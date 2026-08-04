"""LSAST orchestrator: Semgrep detector → normalizer → verifier → fusion → persist.

Returns (visible_findings, filtered_findings) so the caller can render both, and
persists only the visible/needs_review set via the existing save_findings_to_db()
helper (which drops keys not on the Finding model). The legacy file/dashboard
surface is unchanged.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor

from scanner.rag.database import save_findings_to_db
from scanner.rag.finding_normalizer import dedupe_findings, normalize
from scanner.rag.fusion import fuse
from scanner.rag.languages import language_for_path
from scanner.rag.llm import llm_health
from scanner.rag.llm_verifier import verify
from scanner.rag.lsast_types import VerifierVerdict
from scanner.rag.progress import update_progress
from scanner.rag.report_enricher import apply_report, generate_report
from scanner.rag.resume import fingerprint
from scanner.rag.semgrep_detector import run_semgrep

logger = logging.getLogger(__name__)


def _max_workers() -> int:
    """Bounded concurrency for the per-finding LLM work (W6).

    Defaults to 4. The local CPU-only ``llama-server`` serializes inference, so
    the win is overlapping detector/normalize/JSON-parse work with in-flight LLM
    calls rather than true parallel inference — keep the cap small and env-tunable
    (``LSAST_MAX_WORKERS``) so a multi-slot host can raise it. ``1`` forces the
    legacy serial path.
    """
    try:
        return max(1, int(os.getenv("LSAST_MAX_WORKERS", "4")))
    except (ValueError, TypeError):
        return 4


def _process_one(sf, scan_id: str, triggered_by: str, llm_ok: bool = True):
    """Run normalize → verify → fuse → (enrich) for ONE finding.

    Pure compute + LLM I/O only — NO DB writes or progress updates, so it is safe
    to run concurrently in a thread pool. Returns the ``FusionOutcome`` (with the
    enriched finding dict) or ``None`` if this single finding hit an error, so one
    malformed finding can't sink the batch. Honours the fail-open path: when the
    LLM is unavailable the verifier/reporter calls are skipped and the finding is
    preserved as a low-confidence TP for human review.
    """
    try:
        finding_dict, dataflow = normalize(sf, scan_id=scan_id, triggered_by=triggered_by)
        # Resume checkpoint identity -- set unconditionally (independent of
        # llm_ok) so a fail-open finding is still skippable on a later resume.
        finding_dict["fingerprint"] = fingerprint(sf)
        if llm_ok:
            verdict = verify(
                cwe=sf.cwe,
                language=language_for_path(sf.file_path).name,
                dataflow=dataflow,
                code_excerpt=sf.code_excerpt,
            )
        else:
            # Fail-open verdict (same shape the verifier uses) so the finding
            # is preserved for human review instead of dropped.
            verdict = VerifierVerdict(
                verdict="TP",
                reason="LLM unavailable; preserved for review",
                confidence=0.3,
            )
        outcome = fuse(finding_dict, verdict)
    except Exception as exc:  # one malformed finding must not sink the batch
        logger.warning(
            "LSAST: skipping finding %s — processing error: %s",
            getattr(sf, "rule_id", "?"), exc,
        )
        return None

    # Reporting pass: a second, separate LLM call authors the human-facing
    # fields (name / description / impact / remediation). Fail-open — it leaves
    # the deterministic Semgrep-derived fields (rule-name title, message)
    # untouched if the model can't produce a usable report, and never touches
    # CWE / severity / location. Skipped for suppressed findings and when the
    # LLM is unavailable.
    if outcome.action != "suppress" and llm_ok:
        report = generate_report(
            rule_name=outcome.finding.get("title", ""),   # the Semgrep rule name (pre-enrichment)
            cwe=outcome.finding.get("cwe", ""),
            language=language_for_path(sf.file_path).name,
            file_path=sf.file_path,
            line=sf.start_line,
            dataflow=dataflow,
            code_excerpt=sf.code_excerpt,
            detector_note=sf.message,                     # anchor the LLM to the real issue
        )
        apply_report(outcome.finding, report)
    return outcome


def lsast_scan_folder(folder_path: str, scan_id: str, triggered_by: str,
                       skip_fingerprints: frozenset[str] = frozenset(),
                       cancel_event=None,
                      ) -> tuple[list[dict], list[dict]]:
    """Run the full LSAST pipeline. Returns (visible, filtered).

    ``skip_fingerprints`` excludes findings already verified+persisted in a
    prior (crashed/cancelled) attempt at this same scan -- see resume.py.
    ``cancel_event``, when set, is checked between findings so a user-requested
    cancel stops the batch promptly instead of running it to completion.
    """
    sem_findings = run_semgrep(folder_path)
    if not sem_findings:
        logger.info("LSAST: Semgrep produced no findings for %s", folder_path)
        return [], []

    # Collapse duplicate findings (same file/line/CWE flagged by overlapping
    # rules) before the expensive per-finding verify/enrich/persist loop.
    raw_count = len(sem_findings)
    sem_findings = dedupe_findings(sem_findings)
    if len(sem_findings) != raw_count:
        logger.info("LSAST: de-duplicated %d -> %d findings", raw_count, len(sem_findings))

    if skip_fingerprints:
        before = len(sem_findings)
        sem_findings = [sf for sf in sem_findings if fingerprint(sf) not in skip_fingerprints]
        logger.info("LSAST: resume filtered %d -> %d findings (already processed)",
                    before, len(sem_findings))
        if not sem_findings:
            logger.info("LSAST: nothing left to process for %s (resume already complete)",
                        folder_path)
            return [], []

    # One up-front check: can the LLM actually do inference (valid API key)?
    # If not, we keep every deterministic finding but skip the per-finding AI
    # verify/enrich calls — avoids spamming auth errors and records the reason on
    # the scan so the UI can show "AI verification unavailable".
    llm_ok, llm_detail = llm_health()
    if not llm_ok:
        logger.warning(
            "LSAST: LLM unavailable (%s) — keeping deterministic findings, "
            "skipping AI verify/enrich for scan %s", llm_detail, scan_id,
        )
    update_progress(scan_id, extra_metrics={"llm": {"available": llm_ok, "detail": llm_detail}})

    visible: list[dict] = []
    filtered: list[dict] = []

    # The per-finding LLM work (verify + enrich) is the wall-time bottleneck.
    # Run it concurrently across findings with a small, bounded worker pool —
    # the calls are IO-bound (the `requests` HTTP round-trip releases the GIL),
    # so threads overlap them. `_process_one` does NO DB writes, so the pool is
    # thread-safe; persistence + progress stay on this thread, below.
    #
    # `ex.map` preserves input order, so the visible/filtered partition is
    # identical to the serial path regardless of completion order. A single
    # worker (LSAST_MAX_WORKERS=1) or a single finding takes the serial branch.
    workers = _max_workers()
    if workers > 1 and len(sem_findings) > 1:
        with ThreadPoolExecutor(max_workers=workers,
                                thread_name_prefix="lsast") as ex:
            outcomes = list(ex.map(
                lambda sf: _process_one(sf, scan_id, triggered_by, llm_ok),
                sem_findings))
    else:
        outcomes = [_process_one(sf, scan_id, triggered_by, llm_ok)
                    for sf in sem_findings]

    # Partition + persist serially, in detector order, on this thread. Keeping
    # save/progress out of the pool avoids cross-thread DB sessions and keeps the
    # incremental "findings appear live" semantics (count grows as we persist).
    for outcome in outcomes:
        if outcome is None:                 # this finding errored in _process_one
            continue
        if outcome.action == "suppress":
            filtered.append(outcome.finding)
            continue
        visible.append(outcome.finding)

        # A persistence hiccup on one finding must not sink the whole scan.
        try:
            save_findings_to_db([outcome.finding])
            update_progress(scan_id, findings=len(visible))
        except Exception as exc:  # noqa: BLE001
            logger.warning("LSAST: incremental persist failed: %s", exc)

    logger.info(
        "LSAST done: %d Semgrep → %d visible (%d needs_review) + %d filtered",
        len(sem_findings),
        len(visible),
        sum(1 for f in visible if f.get("status") == "needs_review"),
        len(filtered),
    )
    return visible, filtered

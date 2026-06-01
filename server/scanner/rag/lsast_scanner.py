"""LSAST orchestrator: Semgrep detector → normalizer → verifier → fusion → persist.

Returns (visible_findings, filtered_findings) so the caller can render both, and
persists only the visible/needs_review set via the existing save_findings_to_db()
helper (which drops keys not on the Finding model). The legacy file/dashboard
surface is unchanged.
"""
from __future__ import annotations

import logging

from scanner.rag.database import save_findings_to_db
from scanner.rag.finding_normalizer import normalize
from scanner.rag.fusion import fuse
from scanner.rag.languages import language_for_path
from scanner.rag.llm_verifier import verify
from scanner.rag.report_enricher import apply_report, generate_report
from scanner.rag.semgrep_detector import run_semgrep

logger = logging.getLogger(__name__)


def lsast_scan_folder(folder_path: str, scan_id: str, triggered_by: str
                      ) -> tuple[list[dict], list[dict]]:
    """Run the full LSAST pipeline. Returns (visible, filtered)."""
    sem_findings = run_semgrep(folder_path)
    if not sem_findings:
        logger.info("LSAST: Semgrep produced no findings for %s", folder_path)
        return [], []

    visible: list[dict] = []
    filtered: list[dict] = []

    for sf in sem_findings:
        try:
            finding_dict, dataflow = normalize(sf, scan_id=scan_id, triggered_by=triggered_by)
            verdict = verify(
                cwe=sf.cwe,
                language=language_for_path(sf.file_path).name,
                dataflow=dataflow,
                code_excerpt=sf.code_excerpt,
            )
            outcome = fuse(finding_dict, verdict)
        except Exception as exc:  # one malformed finding must not sink the batch
            logger.warning(
                "LSAST: skipping finding %s — processing error: %s",
                getattr(sf, "rule_id", "?"), exc,
            )
            continue
        if outcome.action == "suppress":
            filtered.append(outcome.finding)
        else:
            # Reporting pass: a second, separate LLM call authors the human-facing
            # fields (name / description / impact / remediation). Fail-open — it
            # leaves the deterministic Semgrep-derived fields (rule-name title,
            # message) untouched if the model can't produce a usable report, and
            # never touches CWE / severity / location.
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
            visible.append(outcome.finding)

    if visible:
        save_findings_to_db(visible)

    logger.info(
        "LSAST done: %d Semgrep → %d visible (%d needs_review) + %d filtered",
        len(sem_findings),
        len(visible),
        sum(1 for f in visible if f.get("status") == "needs_review"),
        len(filtered),
    )
    return visible, filtered

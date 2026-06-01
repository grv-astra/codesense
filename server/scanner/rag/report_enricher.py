"""LLM finding-report enrichment — the 'reporting' prompt.

A SECOND, separate LLM pass from the TP/FP verifier. Given a finding's code +
dataflow it AUTHORS the human-facing report shown in the app's finding-details
view: name, description, impact, remediation. Constrained single turn, forced
JSON, fail-open — any failure leaves the deterministic, Semgrep-derived fields
(rule-name title, message) untouched, so enrichment never *degrades* a finding.

Deterministic facts — CWE, severity, file/line, the rule that fired — are NEVER
LLM-authored (a model would hallucinate them); only the descriptive prose is.

Quality is bounded by the bundled model: the shipped astra.gguf is a
fill-in-the-middle code model with a weak instruction-following profile (see the
verifier audit in scripts/eval/BASELINE.md), so expect mixed prose until it is
replaced with an instruction-tuned model. Disable with LSAST_ENRICH_FINDINGS=0.
"""
from __future__ import annotations

import logging
import os

from scanner.rag.llm import get_ready_llm
from scanner.rag.llm_verifier import _extract_json_object
from scanner.rag.lsast_types import DataflowContext, FindingReport

logger = logging.getLogger(__name__)

# The report is longer than the verifier's one-line verdict, so it needs more
# output headroom than the client's default cap.
_REPORT_MAX_TOKENS = 384


def enrichment_enabled() -> bool:
    """Read at call time (not import time) so tests/env can toggle it."""
    return os.getenv("LSAST_ENRICH_FINDINGS", "1") != "0"


def build_report_prompt(*, rule_name: str, cwe: str, language: str,
                        file_path: str, line: int,
                        dataflow: DataflowContext, code_excerpt: str,
                        detector_note: str = "") -> str:
    cwe = cwe or "an unknown CWE"
    excerpt = code_excerpt[:1500]
    # The analyzer's own message anchors the model to the REAL issue and curbs
    # hallucinating a different vuln class from a terse rule slug.
    note = f"Analyzer note: {detector_note[:400]}\n\n" if detector_note else ""
    return (
        f"A static analyzer flagged a {cwe} issue (rule: {rule_name or 'n/a'}) in "
        f"{language} at {file_path}:{line}.\n\n"
        f"{note}"
        f"Dataflow trace:\n{dataflow.render_for_prompt()}\n\n"
        f"Code excerpt:\n```{language}\n{excerpt}\n```\n\n"
        "Write a concise security finding report for a developer. Base it on the "
        "analyzer note and the code; keep EACH field to one sentence; be specific to "
        "this code; do NOT invent a different vulnerability class than the CWE above.\n\n"
        "Respond with ONLY this JSON object, no prose, no code fences:\n"
        '{"name": "<short title, <=80 chars>", "description": "<what the issue is>", '
        '"impact": "<what an attacker could do>", "remediation": "<how to fix it>"}'
    )


def generate_report(*, rule_name: str, cwe: str, language: str,
                    file_path: str, line: int,
                    dataflow: DataflowContext, code_excerpt: str,
                    detector_note: str = "") -> FindingReport | None:
    """Author a finding report via the LLM. Never raises; returns None on any
    failure (call error, disabled, or unparseable output) so the caller falls
    back to the deterministic fields."""
    if not enrichment_enabled():
        return None
    prompt = build_report_prompt(rule_name=rule_name, cwe=cwe, language=language,
                                 file_path=file_path, line=line, dataflow=dataflow,
                                 code_excerpt=code_excerpt, detector_note=detector_note)
    try:
        client = get_ready_llm()
        response = client.invoke({"query": prompt, "max_tokens": _REPORT_MAX_TOKENS}) or {}
    except Exception as exc:        # noqa: BLE001 — fail-open by design
        logger.warning("Finding-report enrichment call failed: %s", exc)
        return None
    raw = (response.get("result") or "").strip()
    report = FindingReport.from_json(_extract_json_object(raw))
    if report is None:
        logger.debug("Report enrichment unparseable; keeping detector fields. raw=%r", raw[:200])
    return report


def apply_report(finding: dict, report: FindingReport | None) -> dict:
    """Overlay an LLM report onto the finding dict, field-by-field, falling back
    to the existing (deterministic) value whenever the model left a field blank.
    Mutates and returns the dict. CWE / severity / location are never touched."""
    if report is None:
        return finding
    if report.name:
        finding["title"] = report.name[:200]
    if report.description:
        finding["description"] = report.description
    if report.impact:
        finding["security_risk"] = report.impact
    if report.remediation:
        finding["mitigation"] = report.remediation
    return finding

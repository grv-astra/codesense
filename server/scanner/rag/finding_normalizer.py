"""Translate a SemgrepFinding into the legacy Finding dict + a DataflowContext.

The legacy Finding shape is defined by scanner/rag/extract.py's
extract_relevant_info() — we keep that shape exactly so the DB schema and
the UI keep working unchanged.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from scanner.rag.lsast_types import DataflowContext, SemgrepFinding

_CVSS_BY_SEVERITY = {
    "critical": ("9.8", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"),
    "high":     ("8.8", "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H"),
    "medium":   ("6.5", "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:L"),
    "low":      ("3.1", "CVSS:3.1/AV:L/AC:H/PR:L/UI:R/S:U/C:L/I:N/A:N"),
}


def build_dataflow_context(f: SemgrepFinding) -> DataflowContext:
    """Distil the verifier-ready source/steps/sink view from a Semgrep finding."""
    if not f.taint_trace:
        lines = f.code_excerpt.splitlines() if f.code_excerpt else []
        return DataflowContext(
            source_line=f.start_line, source_code=lines[0] if lines else "",
            sink_line=f.end_line, sink_code=lines[-1] if lines else "",
            steps=[],
            sanitizers_observed=list(f.sanitizers_observed),
        )
    source_line, source_code = f.taint_trace[0]
    sink_line, sink_code = f.taint_trace[-1]
    steps = list(f.taint_trace[1:-1])
    return DataflowContext(
        source_line=source_line, source_code=source_code,
        sink_line=sink_line, sink_code=sink_code,
        steps=steps,
        sanitizers_observed=list(f.sanitizers_observed),
    )


def _cwe_number(cwe: str) -> str:
    m = re.search(r"CWE-(\d+)", cwe or "")
    return m.group(1) if m else ""


def _rule_name(rule_id: str) -> str:
    """The finding's NAME, taken from Semgrep's rule id (check_id).

    Semgrep namespaces a rule by its path, so the last dotted segment is the
    rule's own name, e.g.
      javascript.lang.security.audit.sqli.node-mysql-sqli.node-mysql-sqli
        -> "node-mysql-sqli"
      generic.dockerfile.security.missing-user.missing-user -> "missing-user"
    Returns "" when there's no rule id.
    """
    segs = [s for s in (rule_id or "").split(".") if s]
    return segs[-1] if segs else ""


def _build_mitigation(f: SemgrepFinding, reference: str) -> str:
    """Deterministic remediation guidance derived from the rule's own metadata.

    Ensures a finding is never blank when LLM enrichment is unavailable (no model
    staged / enrichment disabled). The report-enricher overrides this with
    model-authored remediation whenever it succeeds (report_enricher.apply_report
    only overwrites when its remediation field is non-empty).
    """
    parts: list[str] = []
    if f.fix and f.fix.strip():
        parts.append(f"Suggested fix: {f.fix.strip()}")
    if f.references:
        parts.append("References: " + "; ".join(f.references[:3]))
    if not parts:
        if reference and reference != "NA":
            parts.append(
                f"Review the flagged code against {f.cwe or 'the relevant CWE'} and "
                f"apply the recommended secure-coding fix. See {reference}."
            )
        else:
            parts.append(
                "Review the flagged code and apply the recommended secure-coding "
                "fix for this rule."
            )
    return " ".join(parts)[:1000]


def normalize(f: SemgrepFinding, scan_id: str, triggered_by: str) -> tuple[dict, DataflowContext]:
    """Return (legacy_finding_dict, dataflow_context). The dict matches extract.py's shape."""
    cvss_score, cvss_vector = _CVSS_BY_SEVERITY.get(
        f.severity, ("5.0", "CVSS:3.1/AV:L/AC:H/PR:L/UI:N/S:U/C:L/I:L/A:N"))
    num = _cwe_number(f.cwe or "")
    reference = f"https://cwe.mitre.org/data/definitions/{num}.html" if num else "NA"

    finding = {
        "scan_id": scan_id,
        "cwe": f.cwe or "CWE-Unknown",
        "cvss_vector": cvss_vector,
        "cvss_score": cvss_score,
        "code": "f-" + uuid.uuid4().hex[:8],
        # Name comes from Semgrep's rule (check_id), not the prose message.
        "title": (_rule_name(f.rule_id) or f.message or "Vulnerability")[:200],
        "description": f.message[:1000] if f.message else "",
        "severity": f.severity,
        "file_path": f"{f.file_path} [{f.start_line},{f.end_line}]",
        "code_snip": (f.code_excerpt or "")[:2000],
        "security_risk": f.message[:1000] if f.message else "",   # legacy schema: same text as description for now; verifier enriches later
        "mitigation": _build_mitigation(f, reference),
        "status": "open",
        "deleted": False,
        "approved": False,
        "reference": reference,
        "created_at": datetime.now(timezone.utc),
        "created_by": triggered_by,
        "lines": [f.start_line, f.end_line],
        "affected": f.rule_id,
    }
    return finding, build_dataflow_context(f)

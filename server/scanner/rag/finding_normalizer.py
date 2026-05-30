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
        "title": (f.message or f.rule_id or "Vulnerability")[:200],
        "description": f.message[:1000] if f.message else "",
        "severity": f.severity,
        "file_path": f"{f.file_path} [{f.start_line},{f.end_line}]",
        "code_snip": (f.code_excerpt or "")[:2000],
        "security_risk": f.message[:1000] if f.message else "",   # legacy schema: same text as description for now; verifier enriches later
        "mitigation": "",
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

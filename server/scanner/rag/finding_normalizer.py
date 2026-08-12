"""Translate a SemgrepFinding into the legacy Finding dict + a DataflowContext.

The legacy Finding shape is defined by scanner/rag/extract.py's
extract_relevant_info() — we keep that shape exactly so the DB schema and
the UI keep working unchanged.
"""
from __future__ import annotations

import math
import os
import re
import uuid
from datetime import datetime, timezone

from scanner.rag.lsast_types import DataflowContext, SemgrepFinding

# --- CVSS v3.1 base-score derivation ---------------------------------------
# Previously CVSS was a flat per-severity lookup, so every "high" finding read
# 8.8 (79/86 of a DVWA scan) regardless of vulnerability class. We instead pick
# the CWE's characteristic metric vector and COMPUTE the base score from it, so
# an SQLi (9.8) and a reflected XSS (6.1) — both "high" — get meaningfully
# different, internally-consistent scores. CVSS stays fully deterministic.
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_AC = {"L": 0.77, "H": 0.44}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.0}
_PR_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_CHANGED = {"N": 0.85, "L": 0.68, "H": 0.50}

_METRIC_ORDER = ("AV", "AC", "PR", "UI", "S", "C", "I", "A")


def _m(av, ac, pr, ui, s, c, i, a) -> dict[str, str]:
    return dict(zip(_METRIC_ORDER, (av, ac, pr, ui, s, c, i, a)))


def _roundup(x: float) -> float:
    """CVSS 3.1 roundup: smallest one-decimal number >= x (to 5 dp tolerance)."""
    i = int(round(x * 100000))
    if i % 10000 == 0:
        return i / 100000.0
    return (math.floor(i / 10000) + 1) / 10.0


def _cvss_base_score(m: dict[str, str]) -> float:
    """CVSS v3.1 base score from a parsed metric dict."""
    changed = m["S"] == "C"
    pr = (_PR_CHANGED if changed else _PR_UNCHANGED)[m["PR"]]
    iss = 1 - (1 - _CIA[m["C"]]) * (1 - _CIA[m["I"]]) * (1 - _CIA[m["A"]])
    if changed:
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss * 0.9731 - 0.02) ** 13
    else:
        impact = 6.42 * iss
    exploitability = 8.22 * _AV[m["AV"]] * _AC[m["AC"]] * pr * _UI[m["UI"]]
    if impact <= 0:
        return 0.0
    raw = 1.08 * (impact + exploitability) if changed else (impact + exploitability)
    return _roundup(min(raw, 10.0))


def _vector(m: dict[str, str]) -> str:
    return "CVSS:3.1/" + "/".join(f"{k}:{m[k]}" for k in _METRIC_ORDER)


def _parse_vector(vector: str) -> dict[str, str]:
    return dict(part.split(":", 1) for part in vector.split("/")[1:])


# CWE -> characteristic CVSS 3.1 metric vector. Coarse but class-appropriate;
# the score is computed (never hand-typed) so vector and score never drift.
_CVSS_METRICS_BY_CWE: dict[str, dict[str, str]] = {
    "CWE-89":   _m("N", "L", "N", "N", "U", "H", "H", "H"),  # SQLi            9.8
    "CWE-78":   _m("N", "L", "N", "N", "U", "H", "H", "H"),  # OS command inj  9.8
    "CWE-94":   _m("N", "L", "N", "N", "U", "H", "H", "H"),  # code injection  9.8
    "CWE-95":   _m("N", "L", "N", "N", "U", "H", "H", "H"),  # eval injection  9.8
    "CWE-90":   _m("N", "L", "N", "N", "U", "H", "H", "H"),  # LDAP injection  9.8
    "CWE-502":  _m("N", "L", "N", "N", "U", "H", "H", "H"),  # deserialization 9.8
    "CWE-74":   _m("N", "L", "N", "N", "U", "H", "H", "H"),  # generic inject  9.8
    "CWE-79":   _m("N", "L", "N", "R", "C", "L", "L", "N"),  # XSS             6.1
    "CWE-22":   _m("N", "L", "N", "N", "U", "H", "N", "N"),  # path traversal  7.5
    "CWE-352":  _m("N", "L", "N", "R", "U", "H", "H", "H"),  # CSRF            8.8
    "CWE-918":  _m("N", "L", "N", "N", "U", "H", "H", "N"),  # SSRF            9.1
    "CWE-611":  _m("N", "L", "N", "N", "U", "H", "N", "N"),  # XXE             7.5
    "CWE-601":  _m("N", "L", "N", "R", "C", "L", "L", "N"),  # open redirect   6.1
    "CWE-798":  _m("N", "L", "N", "N", "U", "H", "N", "N"),  # hardcoded creds 7.5
    "CWE-327":  _m("N", "H", "N", "N", "U", "H", "N", "N"),  # weak crypto     5.9
    "CWE-328":  _m("N", "H", "N", "N", "U", "H", "N", "N"),  # weak hash       5.9
    "CWE-330":  _m("N", "H", "N", "N", "U", "L", "L", "N"),  # insecure random 4.8
    "CWE-295":  _m("N", "H", "N", "N", "U", "H", "H", "N"),  # cert validation 7.4
    "CWE-1321": _m("N", "L", "N", "N", "U", "L", "L", "L"),  # proto pollution 7.3
    "CWE-1333": _m("N", "L", "N", "N", "U", "N", "N", "H"),  # ReDoS           7.5
    "CWE-200":  _m("N", "L", "N", "N", "U", "H", "N", "N"),  # info exposure   7.5
}

# Fallback metric vectors when the CWE is unknown/unmapped — keyed by the
# deterministic Semgrep severity. Still computed, so internally consistent.
_CVSS_METRICS_BY_SEVERITY: dict[str, dict[str, str]] = {
    "critical": _m("N", "L", "N", "N", "U", "H", "H", "H"),  # 9.8
    "high":     _m("N", "L", "L", "N", "U", "H", "H", "H"),  # 8.8
    "medium":   _m("N", "L", "L", "N", "U", "L", "L", "L"),  # 6.3
    "low":      _m("N", "H", "N", "R", "U", "L", "N", "N"),  # 3.1
}


def derive_cvss(cwe: str, severity: str) -> tuple[str, str]:
    """Return (score, vector). Class-specific by CWE; severity fallback otherwise."""
    metrics = _CVSS_METRICS_BY_CWE.get((cwe or "").upper().strip())
    if metrics is None:
        metrics = _CVSS_METRICS_BY_SEVERITY.get(
            (severity or "medium").lower(), _CVSS_METRICS_BY_SEVERITY["medium"])
    return f"{_cvss_base_score(metrics):.1f}", _vector(metrics)


def _dedup_rank(f: SemgrepFinding) -> tuple:
    """Higher = keep. Richer dataflow / context wins when two rules collide."""
    return (len(f.taint_trace or []), len(f.code_excerpt or ""),
            1 if (f.fix or "").strip() else 0, len(f.references or []))


def dedupe_findings(findings: list[SemgrepFinding]) -> list[SemgrepFinding]:
    """Collapse findings that flag the SAME issue at the SAME location.

    On DVWA ~23% of findings were one (file, line-range, CWE) flagged by two
    overlapping rules. Keep the most informative one; preserve genuinely distinct
    issues that share a line but differ in CWE. Order-stable (ties keep earlier)."""
    best: dict[tuple, SemgrepFinding] = {}
    order: list[tuple] = []
    for f in findings:
        key = (f.file_path, f.start_line, f.end_line, f.cwe)
        if key not in best:
            best[key] = f
            order.append(key)
        elif _dedup_rank(f) > _dedup_rank(best[key]):
            best[key] = f
    return [best[k] for k in order]


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


def _flow_diagram_strings(dc: DataflowContext) -> list[str]:
    """Human-readable Source/Step/Sink lines for the finding-detail flow-diagram
    widget. Skips entries with no resolvable code so the UI never renders a
    blank node; returns [] when nothing in the trace resolved."""
    lines: list[str] = []
    if dc.source_code:
        lines.append(f"Source (line {dc.source_line}): {dc.source_code}")
    for ln, code in dc.steps:
        if code:
            lines.append(f"Step (line {ln}): {code}")
    if dc.sink_code:
        lines.append(f"Sink (line {dc.sink_line}): {dc.sink_code}")
    return lines


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


_SEVERITY_IMPACT = {
    "critical": "could allow full compromise of the application or host if exploited",
    "high": "could lead to a serious breach of confidentiality, integrity, or availability",
    "medium": "could be leveraged as part of an attack chain to weaken the application's security",
    "low": "poses a limited but real security risk that should be reviewed",
}


def _build_security_risk(f: SemgrepFinding) -> str:
    """Deterministic impact statement, distinct from the description (which holds
    the analyzer's message). LLM enrichment overrides this with model-authored
    impact when it succeeds (report_enricher.apply_report)."""
    sev = (f.severity or "medium").lower()
    cwe = f.cwe or "an unspecified weakness"
    impact = _SEVERITY_IMPACT.get(sev, _SEVERITY_IMPACT["medium"])
    return f"This {sev}-severity {cwe} issue {impact}."


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


def _relativize_path(raw_path: str, scan_root: str) -> str:
    """Strip ``scan_root`` from an absolute detector-reported path.

    The detector (OpenGrep) reports absolute paths when scanned against an
    absolute target, and the scan target is always a per-scan temp directory
    (``.../codesense-media/scans/<scan_id>/source/...``). Left absolute,
    ``file_path`` can never match across two different scans of the same
    project. When ``scan_root`` isn't supplied (legacy callers), this is a
    no-op so existing behavior is unchanged.
    """
    if not scan_root or not raw_path:
        return raw_path
    try:
        if not os.path.isabs(raw_path):
            return raw_path
        rel = os.path.relpath(raw_path, scan_root)
    except ValueError:
        return raw_path
    return rel.replace(os.sep, "/")


def normalize(f: SemgrepFinding, scan_id: str, triggered_by: str,
              scan_root: str = "") -> tuple[dict, DataflowContext]:
    """Return (legacy_finding_dict, dataflow_context). The dict matches extract.py's shape.

    ``scan_root``, when supplied, is stripped from ``f.file_path`` so the
    persisted ``file_path`` is relative to the project root instead of the
    detector's absolute per-scan temp path (see ``_relativize_path``).
    """
    cvss_score, cvss_vector = derive_cvss(f.cwe, f.severity)
    num = _cwe_number(f.cwe or "")
    reference = f"https://cwe.mitre.org/data/definitions/{num}.html" if num else "NA"
    dataflow = build_dataflow_context(f)

    finding = {
        "scan_id": scan_id,
        "first_seen_scan_id": scan_id,
        "cwe": f.cwe or "CWE-Unknown",
        "cvss_vector": cvss_vector,
        "cvss_score": cvss_score,
        "code": "f-" + uuid.uuid4().hex[:8],
        # Name comes from Semgrep's rule (check_id), not the prose message.
        "title": (_rule_name(f.rule_id) or f.message or "Vulnerability")[:200],
        "description": f.message[:1000] if f.message else "",
        "severity": f.severity,
        "file_path": f"{_relativize_path(f.file_path, scan_root)} [{f.start_line},{f.end_line}]",
        # Widened (context-padded) snippet for display when available; falls back to
        # the exact-match excerpt (e.g. source file no longer reachable). The LLM
        # prompts use f.code_excerpt directly, never this field.
        "code_snip": (f.context_code or f.code_excerpt or "")[:2000],
        "code_snip_start_line": f.context_start_line or f.start_line or 0,
        "security_risk": _build_security_risk(f),   # deterministic impact (distinct from description); LLM enriches when available
        "mitigation": _build_mitigation(f, reference),
        "status": "open",
        "deleted": False,
        "approved": False,
        "reference": reference,
        "created_at": datetime.now(timezone.utc),
        "created_by": triggered_by,
        "lines": [f.start_line, f.end_line],
        "affected": f.rule_id,
        # W7 — persisted verifier metadata. rule_id is the detector check_id,
        # cleaned the same way as title (last dotted segment) -- the raw
        # check_id is namespace-prefixed by its rule-pack path (and, for a
        # local rules dir, the full install path on disk), which read as
        # garbled noise in the UI. confidence/verifier_reason are placeholders
        # here and get overwritten by fuse() for any finding the LLM verifier
        # judges (fail-open leaves them).
        "rule_id": _rule_name(f.rule_id) or f.rule_id,
        "confidence": None,
        "verifier_reason": "",
        # Flow-diagram widget data — the same source/steps/sink trace already
        # computed for the verifier prompt, formatted for display and persisted
        # so the finding-detail UI can render it without re-running Semgrep.
        "flow_diagram": _flow_diagram_strings(dataflow),
    }
    return finding, dataflow

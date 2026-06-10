"""Render the balanced scorecard (accuracy + perf + packaging) as markdown.

Values are passed in (measured elsewhere); this module only formats, so it's
unit-testable without an engine/LLM. Missing keys render as 'N/A'. Lives in the
eval package (dev-host only, never bundled) alongside the rest of the harness."""
from __future__ import annotations

_ROWS = [
    ("Detector F1", "detector_f1", "{:.3f}"),
    ("Detector FP-rate", "detector_fp_rate", "{:.3f}"),
    ("Verifier FP-suppression", "verifier_fp_suppression", "{:.3f}"),
    ("Verifier Tier-2 F1", "verifier_f1", "{:.3f}"),
    ("Enrichment parse-rate", "enrichment_parse_rate", "{:.2f}"),
    ("Scan wall-time (p50, s)", "scan_wall_s_p50", "{:.0f}"),
    ("Per-finding LLM latency (s)", "llm_latency_s", "{:.1f}"),
    ("Signed build OK", "build_signed_ok", "{}"),
    ("App size (GB)", "app_size_gb", "{:.1f}"),
]


def render_scorecard(values: dict, *, title: str = "Scorecard") -> str:
    lines = [f"## {title}", "", "| Metric | Value |", "|---|---|"]
    for label, key, fmt in _ROWS:
        v = values.get(key)
        cell = "N/A" if v is None else fmt.format(v)
        lines.append(f"| {label} | {cell} |")
    return "\n".join(lines) + "\n"

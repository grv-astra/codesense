"""Render eval results to markdown."""
from __future__ import annotations


def _row(name: str, m: dict) -> str:
    return (f"| {name} | {m.get('precision',0):.3f} | {m.get('recall',0):.3f} "
            f"| {m.get('f1',0):.3f} | {m.get('fp_rate',0):.3f} "
            f"| {m.get('tp',0)} | {m.get('fp',0)} | {m.get('fn',0)} | {m.get('tn',0)} |")


def render_markdown(title, detector, verifier, per_language, passed, failures) -> str:
    lines = [f"# LSAST Eval — {title}", ""]
    lines.append("## Verdict: " + ("PASS ✅" if passed else "FAIL ❌"))
    if failures:
        lines.append("")
        for f in failures:
            lines.append(f"- {f}")
    lines += ["", "## Stage metrics", "",
              "| Stage | Precision | Recall | F1 | FP-rate | TP | FP | FN | TN |",
              "|---|---|---|---|---|---|---|---|---|",
              _row("Detector (Tier 1)", detector),
              _row("Verifier (Tier 2)", verifier), ""]
    lines += ["## Per-language detector coverage", "",
              "| Language | Recall |", "|---|---|"]
    for lang, m in sorted(per_language.items()):
        lines.append(f"| {lang} | {m.get('recall', 0):.3f} |")
    lines.append("")
    return "\n".join(lines)

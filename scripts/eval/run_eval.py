"""CLI entry for the LSAST eval harness.

Examples:
  # deterministic detector metrics on the curated set (CI):
  cd scripts/eval && PYTHONPATH=../../server python3 run_eval.py --dataset curated --tier detector --gate
  # full run incl. OWASP detector (needs an OWASP checkout):
  PYTHONPATH=../../server OWASP_SRC=/path/testcode OWASP_CSV=/path/expectedresults.csv \\
    python3 run_eval.py --dataset all --tier detector
Run from scripts/eval/. PYTHONPATH must include the repo's server/ so `scanner.*` imports.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # make `eval` importable

from eval.datasets.curated import load_curated                  # noqa: E402
from eval.datasets.owasp_benchmark import parse_expectedresults  # noqa: E402
from eval.metrics import compute, meets_thresholds              # noqa: E402
from eval import runner, report                                  # noqa: E402

EMPTY = {"precision": 0, "recall": 0, "f1": 0, "fp_rate": 0, "tp": 0, "fp": 0, "fn": 0, "tn": 0}


def _scanner():
    """Set up Django and return (run_semgrep, lang_fn) from the real scanner."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codesense.settings")
    import django
    django.setup()
    from scanner.rag.semgrep_detector import run_semgrep
    from scanner.rag.languages import language_for_path
    return run_semgrep, (lambda p: language_for_path(p).name)


def main():
    ap = argparse.ArgumentParser(description="LSAST eval harness")
    ap.add_argument("--dataset", choices=["curated", "owasp", "all"], default="curated")
    ap.add_argument("--tier", choices=["detector", "verifier", "all"], default="detector")
    ap.add_argument("--sample-size", type=int, default=200)
    ap.add_argument("--gate", action="store_true", help="exit 1 if thresholds not met")
    args = ap.parse_args()

    cases = []
    if args.dataset in ("curated", "all"):
        cases += load_curated(HERE / "data" / "curated")
    if args.dataset in ("owasp", "all"):
        csv_p, src = os.getenv("OWASP_CSV"), os.getenv("OWASP_SRC")
        if csv_p and src:
            cases += parse_expectedresults(csv_p, src)
        else:
            print("WARNING: OWASP_CSV/OWASP_SRC unset — skipping OWASP dataset.")

    scan_fn, lang_fn = _scanner()
    det = compute(runner.run_detector_tier(cases, scan_fn=scan_fn))
    by_lang = runner.run_detector_tier_by_language(cases, scan_fn=scan_fn, lang_fn=lang_fn)
    per_language = {lang: compute(c) for lang, c in by_lang.items()}

    if args.tier in ("verifier", "all"):
        print("NOTE: verifier tier needs llama-server; run the sampled pass manually "
              "(see README). build_balanced_sample + run_verifier_tier are unit-tested.")

    passed, failures = meets_thresholds(det)
    md = report.render_markdown(
        title=f"baseline {args.dataset}/{args.tier}",
        detector=det, verifier=dict(EMPTY), per_language=per_language,
        passed=passed, failures=failures,
    )
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out / f"{stamp}.md").write_text(md, encoding="utf-8")
    print(md)
    if args.gate and not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()

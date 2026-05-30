"""Two-tier eval runner.

Tier 1 (detector): run Semgrep over each case's source, count tp/fp/fn/tn vs
ground truth — deterministic, no LLM. Also available grouped by language.
Tier 2 (verifier): run the Astra verifier on a balanced sample, cached by
(cwe, sha1(code)). scan_fn / lang_fn / verify_fn are injected so the logic is
unit-testable without Semgrep, the registry, or llama-server.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from eval.matching import Case, finding_hits_case
from eval.metrics import Counts


def _classify(case: Case, findings: list) -> str:
    flagged = any(finding_hits_case(f, case) for f in (findings or []))
    if case.is_real and flagged:
        return "tp"
    if case.is_real and not flagged:
        return "fn"
    if not case.is_real and flagged:
        return "fp"
    return "tn"


def run_detector_tier(cases: list[Case], scan_fn) -> Counts:
    """scan_fn(source_path) -> list[finding dict]. Returns confusion Counts."""
    c = Counts()
    for case in cases:
        findings = scan_fn(case.source_path)  # called exactly once per case
        kind = _classify(case, findings)
        setattr(c, kind, getattr(c, kind) + 1)
    return c


def run_detector_tier_by_language(cases: list[Case], scan_fn, lang_fn) -> dict:
    """Like run_detector_tier but grouped by lang_fn(source_path) -> language name."""
    by_lang: dict[str, Counts] = {}
    for case in cases:
        lang = lang_fn(case.source_path)
        bucket = by_lang.setdefault(lang, Counts())
        findings = scan_fn(case.source_path)  # called exactly once per case
        kind = _classify(case, findings)
        setattr(bucket, kind, getattr(bucket, kind) + 1)
    return by_lang


def build_balanced_sample(cases: list[Case], per_class: int) -> list[Case]:
    """Take up to per_class real + per_class fake cases (stable order)."""
    reals = [c for c in cases if c.is_real][:per_class]
    fakes = [c for c in cases if not c.is_real][:per_class]
    return reals + fakes


def _cache_key(cwe: str, code: str) -> str:
    return f"{cwe}:{hashlib.sha1(code.encode('utf-8')).hexdigest()}"


def run_verifier_tier(samples: list, verify_fn, cache_path=None) -> Counts:
    """Run the verifier on sampled findings with ground-truth labels.

    Each sample: {"cwe","language","dataflow","code","is_real"}.
    verify_fn(**kwargs) -> object with .verdict in {"TP","FP"}.
    real kept(TP)=tp; real dropped(FP)=fn; fake dropped(FP)=tn; fake kept(TP)=fp.
    Verdicts cached by (cwe, sha1(code)).
    """
    cache = {}
    cpath = Path(cache_path) if cache_path else None
    if cpath and cpath.exists():
        cache = json.loads(cpath.read_text(encoding="utf-8"))

    c = Counts()
    for s in samples:
        key = _cache_key(s["cwe"], s["code"])
        if key in cache:
            verdict = cache[key]
        else:
            verdict = verify_fn(cwe=s["cwe"], language=s.get("language", "text"),
                                dataflow=s["dataflow"], code_excerpt=s["code"]).verdict
            cache[key] = verdict
        kept = (verdict == "TP")
        if s["is_real"] and kept:
            c.tp += 1
        elif s["is_real"] and not kept:
            c.fn += 1
        elif not s["is_real"] and not kept:
            c.tn += 1
        else:
            c.fp += 1

    if cpath:
        cpath.parent.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return c

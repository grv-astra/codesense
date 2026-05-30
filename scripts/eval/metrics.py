"""Pure metric math for the LSAST eval harness. No I/O, no deps."""
from __future__ import annotations

from dataclasses import dataclass

# §9 acceptance thresholds.
THRESHOLDS = {"f1": 0.70, "recall": 0.60, "fp_rate_max": 0.25}


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def compute(c: Counts) -> dict[str, float]:
    precision = _safe_div(c.tp, c.tp + c.fp)
    recall = _safe_div(c.tp, c.tp + c.fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    fp_rate = _safe_div(c.fp, c.fp + c.tn)
    return {
        "tp": c.tp, "fp": c.fp, "fn": c.fn, "tn": c.tn,
        "precision": precision, "recall": recall, "f1": f1, "fp_rate": fp_rate,
    }


def meets_thresholds(metrics: dict) -> tuple[bool, list[str]]:
    """Return (passed, [failure messages]) vs the §9 acceptance criteria."""
    failures = []
    if metrics.get("f1", 0.0) < THRESHOLDS["f1"]:
        failures.append(f"f1 {metrics.get('f1', 0):.3f} < {THRESHOLDS['f1']}")
    if metrics.get("recall", 0.0) < THRESHOLDS["recall"]:
        failures.append(f"recall {metrics.get('recall', 0):.3f} < {THRESHOLDS['recall']}")
    if metrics.get("fp_rate", 1.0) > THRESHOLDS["fp_rate_max"]:
        failures.append(f"fp_rate {metrics.get('fp_rate', 1.0):.3f} > {THRESHOLDS['fp_rate_max']}")
    return (not failures, failures)

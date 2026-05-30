"""Combine Semgrep severity + LLM verdict into a display decision (design spec §7).

`confidence` = the verifier's confidence in its own verdict. Severity is a
SEPARATE axis ("how bad if real"), kept in the finding's `severity` field — we do
NOT fold it into confidence, so a fail-open low-confidence TP stays visibly
uncertain rather than being inflated by a high severity.

Rules:
  LLM=TP, any severity                 -> show; confidence = verdict.confidence
  LLM=FP, severity in {low, medium}    -> suppress (status="filtered")
  LLM=FP, severity in {high, critical} -> needs_review (never drop a high-severity
                                          finding on a 3B model's say-so)
"""
from __future__ import annotations

from dataclasses import dataclass

from scanner.rag.lsast_types import VerifierVerdict

# Severity ranking; anything unlisted is treated as "medium" (rank 2).
_NUMERIC_SEVERITY = {"low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class FusionOutcome:
    """Decision for one finding. `finding` is the (annotated) legacy Finding dict."""
    action: str        # "show" | "suppress" | "needs_review"
    finding: dict


def fuse(finding: dict, verdict: VerifierVerdict) -> FusionOutcome:
    sev = (finding.get("severity") or "medium").lower()
    finding["confidence"] = verdict.confidence
    finding["verifier_reason"] = verdict.reason

    if verdict.verdict == "TP":
        return FusionOutcome(action="show", finding=finding)

    # verdict.verdict == "FP"
    if _NUMERIC_SEVERITY.get(sev, 2) >= 3:    # high or critical
        finding["status"] = "needs_review"
        finding["title"] = f"[verifier:FP] {finding.get('title', '')}"[:200]
        return FusionOutcome(action="needs_review", finding=finding)

    finding["status"] = "filtered"
    return FusionOutcome(action="suppress", finding=finding)

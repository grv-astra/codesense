"""Constrained LLM verifier.

The LLM never produces a finding from scratch — it judges TP/FP on a Semgrep
finding given the dataflow context. Single turn, no agent loop, no risk hints,
forced JSON output, strict parser, fail-open on parse / call failure.
"""
from __future__ import annotations

import logging
import re

from scanner.rag.llm import get_ready_llm
from scanner.rag.lsast_types import DataflowContext, VerifierVerdict

logger = logging.getLogger(__name__)


def build_verifier_prompt(*, cwe: str, language: str,
                          dataflow: DataflowContext, code_excerpt: str) -> str:
    """Build the verifier prompt. The dataflow trace is the new signal vs. legacy."""
    cwe = cwe or "an unknown CWE"
    excerpt = code_excerpt[:1800]
    return (
        f"A static dataflow analyzer flagged a potential {cwe} finding.\n\n"
        f"Dataflow trace:\n{dataflow.render_for_prompt()}\n\n"
        f"Code excerpt ({language}):\n"
        f"```{language}\n{excerpt}\n```\n\n"
        "QUESTION: Is this finding a TRUE positive or a FALSE positive? Consider whether "
        "any sanitizer / parameterization / ORM / framework-level escaping makes the sink safe.\n\n"
        "Respond with ONLY this JSON object, no prose, no code fences:\n"
        '{"verdict": "TP" | "FP", "reason": "<one short sentence>", "confidence": 0.0-1.0}'
    )


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(raw: str) -> str:
    """Pull the JSON object out of the model's reply, tolerating code fences / prose."""
    if not raw:
        return ""
    fenced = _JSON_FENCE_RE.search(raw)
    if fenced:
        return fenced.group(1).strip()
    found = _JSON_OBJECT_RE.search(raw)
    return found.group(0).strip() if found else raw.strip()


def verify(*, cwe: str, language: str,
           dataflow: DataflowContext, code_excerpt: str) -> VerifierVerdict:
    """Classify a Semgrep finding as TP/FP. Never raises.

    Fail-open: any failure returns a low-confidence TP so the finding is preserved
    for human review rather than silently dropped.
    """
    prompt = build_verifier_prompt(cwe=cwe, language=language,
                                   dataflow=dataflow, code_excerpt=code_excerpt)
    fail_open = VerifierVerdict(verdict="TP",
                                reason="verifier unparseable; preserved for review",
                                confidence=0.3)
    try:
        client = get_ready_llm()
        response = client.invoke(
            {"query": prompt, "response_format": {"type": "json_object"}}
        ) or {}
    except Exception as exc:        # noqa: BLE001 — fail-open by design
        logger.warning("LLM verifier call failed: %s", exc)
        return fail_open

    raw = (response.get("result") or "").strip()
    parsed = VerifierVerdict.from_json(_extract_json_object(raw))
    if parsed is None:
        logger.debug("Verifier response unparseable, failing open. raw=%r", raw[:200])
        return fail_open
    return parsed

"""Typed payloads for the LSAST pipeline.

Three small dataclasses that pass between the detector → normalizer → verifier
→ fusion stages. Keep them dumb: data only, no side effects, no I/O. Anything
that needs to do work lives in a dedicated module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class SemgrepFinding:
    """One finding emitted by Semgrep, parsed from its --json output."""
    rule_id: str
    cwe: str                          # e.g. "CWE-89"; "" if rule has no cwe metadata
    severity: str                     # "low" | "medium" | "high" | "critical"
    message: str
    file_path: str
    start_line: int
    end_line: int
    code_excerpt: str
    taint_trace: list[tuple[int, str]] = field(default_factory=list)  # (line, code) per step
    sanitizers_observed: list[str] = field(default_factory=list)      # rule-reported sanitizers
    references: list[str] = field(default_factory=list)               # rule metadata.references URLs
    fix: str = ""                                                     # rule autofix suggestion, if any


@dataclass
class DataflowContext:
    """The verifier-ready dataflow summary distilled from a SemgrepFinding."""
    source_line: int
    source_code: str
    sink_line: int
    sink_code: str
    steps: list[tuple[int, str]] = field(default_factory=list)        # intermediate steps
    sanitizers_observed: list[str] = field(default_factory=list)

    def render_for_prompt(self) -> str:
        lines = [f"  Source : {self.source_code}     line {self.source_line}"]
        for ln, code in self.steps:
            lines.append(f"  → step : {code}     line {ln}")
        lines.append(f"  → Sink : {self.sink_code}     line {self.sink_line}")
        sans = ", ".join(self.sanitizers_observed) if self.sanitizers_observed else "none"
        lines.append(f"Sanitizers observed in trace: {sans}")
        return "\n".join(lines)


_ALLOWED_VERDICTS = {"TP", "FP"}


@dataclass
class VerifierVerdict:
    """Parsed verdict from the LLM verifier. None when parsing fails."""
    verdict: str           # "TP" | "FP"
    reason: str
    confidence: float

    @classmethod
    def from_json(cls, raw: str) -> "VerifierVerdict | None":
        """Strict parse: returns None on any malformedness."""
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if not isinstance(obj, dict):
            return None
        verdict = obj.get("verdict")
        if verdict not in _ALLOWED_VERDICTS:
            return None
        try:
            conf = float(obj.get("confidence", 0.0))
        except (ValueError, TypeError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        reason = str(obj.get("reason", ""))[:200]
        return cls(verdict=verdict, reason=reason, confidence=conf)


@dataclass
class FindingReport:
    """LLM-authored, human-facing finding report (the 'reporting' pass).

    Any field may be "" — the caller then keeps the deterministic, Semgrep-derived
    value, so a weak/garbled model degrades gracefully instead of blanking a field.
    """
    name: str
    description: str
    impact: str
    remediation: str

    @classmethod
    def from_json(cls, raw: str) -> "FindingReport | None":
        """Lenient parse: None only if the payload isn't a JSON object. Tolerates
        alternate key names the model may emit (title/risk/mitigation/fix)."""
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            return None
        if not isinstance(obj, dict):
            return None

        def pick(*keys: str, limit: int) -> str:
            for k in keys:
                v = obj.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()[:limit]
            return ""

        return cls(
            name=pick("name", "title", limit=120),
            description=pick("description", "desc", "summary", limit=1000),
            impact=pick("impact", "security_risk", "risk", limit=1000),
            remediation=pick("remediation", "mitigation", "fix", "recommendation", limit=1000),
        )

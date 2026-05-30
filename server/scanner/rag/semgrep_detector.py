"""Run Semgrep over a folder and parse its --json output into SemgrepFinding objects.

The detector is intentionally narrow: it shells out to the Semgrep binary,
captures stdout, and translates the JSON to our dataclass. No filtering, no
heuristics, no LLM — those live in downstream modules.
"""
from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from scanner.rag.lsast_types import SemgrepFinding
from scanner.services.tools import get_semgrep_bin, get_semgrep_rules_dir

logger = logging.getLogger(__name__)

_SEVERITY_MAP = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}

_DEFAULT_REGISTRY_PACKS = ["p/security-audit", "p/owasp-top-ten", "p/secrets"]

_TIMEOUT_SECONDS = 300


def _extract_cwe(metadata: dict[str, Any]) -> str:
    cwes = metadata.get("cwe") or []
    if isinstance(cwes, str):
        cwes = [cwes]
    for entry in cwes:
        if not isinstance(entry, str):
            continue
        head = entry.split(":", 1)[0].strip()
        if head.startswith("CWE-"):
            return head
    return ""


def _extract_taint_trace(extra: dict[str, Any]) -> list[tuple[int, str]]:
    trace: list[tuple[int, str]] = []
    df = extra.get("dataflow_trace") or {}

    def _append(items, code_key: str):
        for item in items or []:
            loc = item.get("start") or item.get("location") or {}
            line = loc.get("line") if isinstance(loc, dict) else None
            code = item.get(code_key) or item.get("code") or ""
            if isinstance(line, int) and isinstance(code, str):
                trace.append((line, code.strip()))

    _append(df.get("taint_source"), "code")
    _append(df.get("intermediate_vars"), "content")
    _append(df.get("taint_sink"), "code")
    return trace


def parse_semgrep_json(raw: str) -> list[SemgrepFinding]:
    try:
        doc = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("Could not parse Semgrep JSON output")
        return []
    if not isinstance(doc, dict):
        return []

    findings: list[SemgrepFinding] = []
    for r in doc.get("results", []) or []:
        if not isinstance(r, dict):
            continue
        extra = r.get("extra") or {}
        metadata = extra.get("metadata") or {}
        severity_raw = (extra.get("severity") or "").upper()
        try:
            findings.append(SemgrepFinding(
                rule_id=str(r.get("check_id", "")),
                cwe=_extract_cwe(metadata),
                severity=_SEVERITY_MAP.get(severity_raw, "medium"),
                message=str(extra.get("message", "")),
                file_path=str(r.get("path", "")),
                start_line=int((r.get("start") or {}).get("line", 0)),
                end_line=int((r.get("end") or {}).get("line", 0)),
                code_excerpt=str(extra.get("lines", "")),
                taint_trace=_extract_taint_trace(extra),
                sanitizers_observed=[],
            ))
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping malformed Semgrep result: %s", exc)
            continue
    return findings


def run_semgrep(folder_path: str) -> list[SemgrepFinding]:
    bin_path = get_semgrep_bin()
    rules_dir = get_semgrep_rules_dir()

    cmd = [bin_path]
    if rules_dir:
        cmd += ["--config", rules_dir]
    else:
        for pack in _DEFAULT_REGISTRY_PACKS:
            cmd += ["--config", pack]
    cmd += ["--json", "--quiet", "--metrics", "off", "--disable-version-check", folder_path]

    logger.info("Running Semgrep: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS, check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("Semgrep invocation failed: %s", exc)
        return []

    if result.returncode >= 2:
        logger.warning("Semgrep failed (rc=%d): %s", result.returncode, result.stderr[:500])
        return []

    return parse_semgrep_json(result.stdout)

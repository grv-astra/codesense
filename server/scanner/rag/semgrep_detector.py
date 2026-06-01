"""Run Semgrep over a folder and parse its --json output into SemgrepFinding objects.

The detector is intentionally narrow: it shells out to the Semgrep binary,
captures stdout, and translates the JSON to our dataclass. No filtering, no
heuristics, no LLM — those live in downstream modules.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
from typing import Any

from scanner.rag.lsast_types import SemgrepFinding
from scanner.services.tools import get_semgrep_bin, get_semgrep_rules_dir

logger = logging.getLogger(__name__)

_SEVERITY_MAP = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}

_DEFAULT_REGISTRY_PACKS = ["p/security-audit", "p/owasp-top-ten", "p/secrets"]

_TIMEOUT_SECONDS = 300


def _extract_cwe(metadata: dict[str, Any]) -> str:
    """The explicit CWE from rule metadata (handles str / int / list / 'CWE-89: ...')."""
    cwes = metadata.get("cwe")
    if isinstance(cwes, (str, int)):
        cwes = [cwes]
    for entry in cwes or []:
        if isinstance(entry, int):
            return f"CWE-{entry}"
        if not isinstance(entry, str):
            continue
        m = re.search(r"CWE[-_ ]?(\d+)", entry, re.IGNORECASE)
        if m:
            return f"CWE-{m.group(1)}"
        head = entry.split(":", 1)[0].strip()
        if head.isdigit():
            return f"CWE-{head}"
    return ""


# Rule-name keyword -> CWE, matched as substrings against the (lowercased) Semgrep
# check_id, most-specific first. Keys are deliberately long/unambiguous so they
# don't collide with path noise in a local --config check_id (e.g. NO bare "rce":
# it lurks inside "souRCE"). Guarded by test_rule_id_keyword_does_not_misfire.
_RULE_ID_CWE: tuple[tuple[str, str], ...] = (
    ("sql-injection", "CWE-89"), ("sqli", "CWE-89"), ("tainted-sql", "CWE-89"),
    ("command-injection", "CWE-78"), ("os-command", "CWE-78"),
    ("code-injection", "CWE-94"), ("eval-injection", "CWE-95"),
    ("non-literal-require", "CWE-95"),
    ("path-traversal", "CWE-22"), ("path-join", "CWE-22"),
    ("directory-traversal", "CWE-22"), ("zip-slip", "CWE-22"),
    ("cross-site-scripting", "CWE-79"), ("xss", "CWE-79"),
    ("csrf", "CWE-352"), ("csurf", "CWE-352"),
    ("ssrf", "CWE-918"), ("server-side-request", "CWE-918"),
    ("xxe", "CWE-611"), ("xml-external", "CWE-611"),
    ("open-redirect", "CWE-601"),
    ("deserial", "CWE-502"),
    ("prototype-pollution", "CWE-1321"),
    ("ldap-injection", "CWE-90"),
    ("redos", "CWE-1333"), ("regex-dos", "CWE-1333"),
    ("hardcoded-secret", "CWE-798"), ("jwt-secret", "CWE-798"),
    ("hardcoded", "CWE-798"), ("hard-coded", "CWE-798"),
    ("weak-hash", "CWE-328"), ("insecure-hash", "CWE-328"),
    ("weak-crypto", "CWE-327"), ("insecure-cipher", "CWE-327"),
    ("insecure-random", "CWE-330"), ("math-random", "CWE-330"),
    ("disable-cert", "CWE-295"), ("verify-false", "CWE-295"),
    ("missing-user", "CWE-250"), ("no-new-privileges", "CWE-250"),
    ("privileged", "CWE-250"), ("writable-filesystem", "CWE-732"),
)

# OWASP category keyword -> representative CWE, matched against the (lowercased)
# owasp tag(s). Coarse (one OWASP category spans many CWEs) but far better than
# Unknown. XSS / SSRF / XXE listed before the broad "injection" so they win.
_OWASP_CWE: tuple[tuple[str, str], ...] = (
    ("cross-site scripting", "CWE-79"),
    ("server-side request forgery", "CWE-918"),
    ("xml external entit", "CWE-611"),
    ("injection", "CWE-74"),
    ("sensitive data exposure", "CWE-200"),
    ("cryptographic failure", "CWE-327"),
    ("broken access control", "CWE-284"),
    ("identification and authentication", "CWE-287"),
    ("broken authentication", "CWE-287"),
    ("vulnerable and outdated", "CWE-1104"),
    ("known vulnerabilit", "CWE-1104"),
    ("insecure design", "CWE-657"),
    ("software and data integrity", "CWE-345"),
    ("logging and monitoring", "CWE-778"),
    ("security misconfiguration", "CWE-16"),
    ("misconfiguration", "CWE-16"),
)

# Non-security rule categories -> generic coding-standards CWE, so quality/lint
# rules read as "coding standard" rather than the misleading "unknown vuln".
_NON_SECURITY_CATEGORIES = frozenset(
    {"correctness", "best-practice", "maintainability", "performance", "portability"})


def _cwe_from_rule_id(rule_id: str) -> str:
    rid = (rule_id or "").lower()
    for needle, cwe in _RULE_ID_CWE:
        if needle in rid:
            return cwe
    return ""


def _cwe_from_owasp(metadata: dict[str, Any]) -> str:
    owasp = metadata.get("owasp")
    if isinstance(owasp, (str, int)):
        owasp = [owasp]
    blob = " ".join(str(x) for x in (owasp or [])).lower()
    for needle, cwe in _OWASP_CWE:
        if needle in blob:
            return cwe
    return ""


def _cwe_from_category(metadata: dict[str, Any]) -> str:
    cat = str(metadata.get("category") or "").strip().lower()
    return "CWE-710" if cat in _NON_SECURITY_CATEGORIES else ""   # coding standards


def derive_cwe(metadata: dict[str, Any], rule_id: str) -> str:
    """Best-effort CWE: explicit metadata, else rule-name keyword, else OWASP tag,
    else a coding-standards CWE for non-security categories. Returns '' when
    nothing fits (the caller renders that as CWE-Unknown)."""
    return (_extract_cwe(metadata)
            or _cwe_from_rule_id(rule_id)
            or _cwe_from_owasp(metadata)
            or _cwe_from_category(metadata))


def _find_loc_and_code(node: Any) -> tuple[int | None, str]:
    """Best-effort (line, code) from one dataflow-trace node. Never raises.

    Handles BOTH engine shapes:
      * Semgrep:  {"start": {"line": N}, "code"/"content": "..."}
      * OpenGrep: ["CliLoc", [{"start": {"line": N}, ...}, "code"]]  (OCaml tagged
        tuple — item[0] is a string tag, NOT a location dict).
    """
    line: int | None = None
    code = ""
    stack = [node]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            for lk in ("start", "location"):   # Semgrep uses both across node kinds
                loc = x.get(lk)
                if line is None and isinstance(loc, dict) and isinstance(loc.get("line"), int):
                    line = loc["line"]
            for key in ("code", "content"):
                v = x.get(key)
                if not code and isinstance(v, str) and v:
                    code = v
            stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
        elif isinstance(x, list):
            stack.extend(x)
        elif isinstance(x, str) and not code and x != "CliLoc":
            code = x
    return line, code.strip()


def _extract_taint_trace(extra: dict[str, Any]) -> list[tuple[int, str]]:
    """Distil a (line, code) taint path from Semgrep/OpenGrep dataflow_trace.

    Defensive by design: engines disagree on the JSON shape (Semgrep emits a list
    of location dicts; OpenGrep emits a single ['CliLoc', [...]] tagged tuple), and
    a malformed node must never sink the whole scan.
    """
    df = extra.get("dataflow_trace")
    if not isinstance(df, dict):
        return []
    trace: list[tuple[int, str]] = []
    for key in ("taint_source", "intermediate_vars", "taint_sink"):
        raw = df.get(key)
        if not isinstance(raw, list) or not raw:
            continue
        # A leading string tag (OpenGrep "CliLoc") means the whole list is ONE node;
        # otherwise it's Semgrep's list of node dicts.
        nodes = [raw] if isinstance(raw[0], str) else raw
        for n in nodes:
            line, code = _find_loc_and_code(n)
            if isinstance(line, int):
                trace.append((line, code))
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
    for r in doc.get("results", []) or []:   # `or []` guards an explicit "results": null
        if not isinstance(r, dict):
            continue
        extra = r.get("extra")
        if not isinstance(extra, dict):
            extra = {}
        metadata = extra.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        severity_raw = (extra.get("severity") or "").upper()
        check_id = str(r.get("check_id", ""))
        try:
            findings.append(SemgrepFinding(
                rule_id=check_id,
                cwe=derive_cwe(metadata, check_id),
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
    # No "--metrics off": the bundled engine is OpenGrep, which has no telemetry
    # and rejects that flag (rc=2). Upstream Semgrep (dev/eval) telemetry is
    # disabled via SEMGREP_SEND_METRICS in the env below instead.
    cmd += ["--json", "--quiet", "--disable-version-check", folder_path]

    # Force a UTF-8 environment. The frozen OpenGrep/Semgrep reads rule YAMLs
    # using the process locale; a non-UTF-8 host locale makes it fall back to
    # the ASCII codec and crash (UnicodeDecodeError) on rules containing
    # non-ASCII bytes (em-dashes, smart quotes, …). C.UTF-8 is portable across
    # macOS/Linux; PYTHONUTF8 covers Windows.
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["LC_ALL"] = "C.UTF-8"
    env["LANG"] = "C.UTF-8"
    env["SEMGREP_SEND_METRICS"] = "off"

    logger.info("Running Semgrep: %s", shlex.join(cmd))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_TIMEOUT_SECONDS,
            check=False, env=env,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("Semgrep invocation failed: %s", exc)
        return []

    if result.returncode >= 2:
        logger.warning("Semgrep failed (rc=%d): %s", result.returncode, result.stderr[:500])
        return []

    return parse_semgrep_json(result.stdout)

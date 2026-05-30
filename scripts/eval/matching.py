"""Match scanner findings to benchmark cases by file + CWE family."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

# Unlisted CWEs map to themselves (dict.get(n, n)); only aliases need entries.
# CWE families: alias variants → a canonical CWE for family comparison.
_FAMILY_ALIASES = {
    943: 89,   # improper neutralization in a data query → SQLi
    564: 89,   # SQL injection: hibernate → SQLi
    78: 78,    # OS command injection
    77: 78,    # command injection → OS command injection family
    80: 79,    # basic XSS → XSS
    83: 79,
    22: 22,    # path traversal
    23: 22, 36: 22,
    327: 327, 328: 327,  # weak crypto/hash family
}


@dataclass
class Case:
    case_id: str
    source_path: str
    is_real: bool
    cwe: str


def cwe_number(cwe: str) -> int | None:
    m = re.search(r"CWE-(\d+)", cwe or "")
    return int(m.group(1)) if m else None


def _canon(n: int | None) -> int | None:
    return _FAMILY_ALIASES.get(n, n)


def same_cwe_family(a: str, b: str) -> bool:
    na, nb = _canon(cwe_number(a)), _canon(cwe_number(b))
    return na is not None and na == nb


def _get(finding, key: str) -> str:
    """Read a field from a finding that may be a dict OR an object with attrs."""
    if isinstance(finding, dict):
        return finding.get(key, "") or ""
    return getattr(finding, key, "") or ""


def _finding_file(finding) -> str:
    # finding's file_path may be "<path> [start,end]" (normalized dict) or a bare
    # path (raw SemgrepFinding) — strip a trailing [n,m] suffix if present.
    raw = _get(finding, "file_path")
    return re.sub(r"\s*\[\d+,\d+\]\s*$", "", raw).strip()


def finding_hits_case(finding, case: Case) -> bool:
    """A finding (dict or SemgrepFinding) hits a case if same source file + CWE family."""
    # Basename-only match: OWASP/curated filenames are unique, so this is safe;
    # same-named files in different dirs would collide.
    if os.path.basename(_finding_file(finding)) != os.path.basename(case.source_path):
        return False
    return same_cwe_family(_get(finding, "cwe"), case.cwe)

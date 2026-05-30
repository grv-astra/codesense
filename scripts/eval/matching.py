"""Match scanner findings to benchmark cases by file + CWE family."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

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


def _finding_file(finding: dict) -> str:
    raw = finding.get("file_path", "")
    return re.sub(r"\s*\[\d+,\d+\]\s*$", "", raw).strip()


def finding_hits_case(finding: dict, case: Case) -> bool:
    """A finding hits a case if it's in the same source file and CWE family."""
    if os.path.basename(_finding_file(finding)) != os.path.basename(case.source_path):
        return False
    return same_cwe_family(finding.get("cwe", ""), case.cwe)

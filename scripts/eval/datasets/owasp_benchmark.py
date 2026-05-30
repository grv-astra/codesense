"""Adapter for the OWASP Benchmark (Java) — github.com/OWASP-Benchmark/BenchmarkJava.

The repo ships an expectedresults CSV (test name, category, real?, cwe). We parse
it into Case objects; source files live under <repo>/src/main/java/org/owasp/
benchmark/testcode/<TestName>.java. Download the repo separately (see README);
this adapter only reads a provided checkout/CSV (no network in the harness code).
"""
from __future__ import annotations

import csv
from pathlib import Path

from eval.matching import Case


def parse_expectedresults(csv_path, src_root: str) -> list[Case]:
    """Parse an OWASP Benchmark expectedresults CSV into Case objects."""
    cases = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if not row or row[0].lstrip().startswith("#"):
                continue
            name = row[0].strip()
            if not name or len(row) < 4:
                continue
            is_real = row[2].strip().lower() == "true"
            cwe = f"CWE-{row[3].strip()}"
            cases.append(Case(
                case_id=name,
                source_path=str(Path(src_root) / f"{name}.java"),
                is_real=is_real,
                cwe=cwe,
            ))
    return cases

"""Load the curated multi-language eval set (FP-rate + coverage probe)."""
from __future__ import annotations

import json
from pathlib import Path

from eval.matching import Case


def load_curated(data_dir) -> list[Case]:
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    cases = []
    for c in manifest.get("cases", []):
        cases.append(Case(
            case_id=c["case_id"],
            source_path=str(data_dir / c["file"]),
            is_real=(c["label"] == "real"),
            cwe=c["cwe"],
        ))
    return cases

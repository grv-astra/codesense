"""Resume/checkpoint support for interrupted LSAST scans.

A "fingerprint" identifies one raw Semgrep finding independent of message/
severity wording, so a resumed run can tell which findings were already
verified+persisted in a prior attempt and skip re-running the expensive LLM
step for them.
"""
from __future__ import annotations

import hashlib

from scanner.rag.lsast_types import SemgrepFinding


def fingerprint(sf: SemgrepFinding) -> str:
    """Stable identity for one raw detector finding: file + line + rule.

    Deliberately independent of message/severity/CWE text (a rules-pack
    wording update shouldn't invalidate an existing checkpoint) -- file_path +
    start_line + rule_id is what actually identifies "the same match" across
    two detector runs over the same source.

    Joined with a NUL byte, not ":" -- NUL can't appear in a filename on any
    platform, so unlike a plain "f:g:h" string join this can't produce the
    same fingerprint for two different (file_path, start_line, rule_id)
    triples via a differently-placed delimiter (e.g. a colon inside a POSIX
    filename).
    """
    raw = "\x00".join((sf.file_path, str(sf.start_line), sf.rule_id))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

"""Resume/checkpoint support for interrupted LSAST scans.

A "fingerprint" identifies one raw Semgrep finding independent of message/
severity wording, so a resumed run can tell which findings were already
verified+persisted in a prior attempt and skip re-running the expensive LLM
step for them.
"""
from __future__ import annotations

import hashlib

from local.api_app.models.orm import Finding, Scan
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


def already_done_fingerprints(scan_id: str) -> frozenset[str]:
    """Fingerprints already persisted for this scan -- what a resume should skip."""
    return frozenset(
        Finding.objects.filter(scan_id=scan_id)
        .exclude(fingerprint="")
        .values_list("fingerprint", flat=True)
    )


def find_orphaned_scans():
    """Scans still queued/in_progress -- by construction, crash leftovers from a
    prior process (a fresh process hasn't started anything itself yet), unless
    it's this same call's own reconciliation running twice -- callers should
    only invoke this once, at real server startup (see run_server.py)."""
    return Scan.objects.filter(status__in=["queued", "in_progress"], deleted=False)


def reconcile_orphaned_scans() -> int:
    """Relabel crash-orphaned scan rows so the UI reflects reality instead of a
    permanently-stuck "queued"/"in_progress". Source/findings are left exactly
    as they were -- this only changes the status label. Returns how many rows
    were reconciled."""
    count = 0
    for scan in find_orphaned_scans():
        new_status = "cancelled" if scan.cancel_requested else "interrupted"
        Scan.objects.filter(id=scan.id).update(status=new_status)
        count += 1
    return count

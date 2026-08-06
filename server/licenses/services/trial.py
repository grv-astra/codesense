"""Trial gate: cap the number of successfully-completed scans per type -- code
(SAST) and SBOM each get their OWN counter/limit, so using up one doesn't
consume the other's allowance.

Enabled only when ``TRIAL_MODE=true`` (off by default, so normal/production
deployments are unlimited). The counts live in a single monotonic ``TrialUsage``
row — independent of the (hard-deletable) Scan/SbomScan rows — so a client
cannot reset the trial by deleting scans. Enforcement is server-side; the UI
count is UX.

Counting policy: a slot is consumed only on SUCCESSFUL completion
(``record_completion`` is called from each pipeline's completion step, which
failed scans never reach). In-progress/queued/interrupted scans of a given
type are counted against THAT type's limit at creation time (and while
pending resume) so concurrent submissions can't overshoot the cap. A
user-cancelled scan does NOT count -- same as a failed one, no slot was ever
completed.
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from local.api_app.models.orm import Scan, SbomScan, TrialUsage

_ACTIVE_STATUSES = ("queued", "in_progress", "interrupted")
_DEFAULT_LIMIT = 2

CODE = "code"
SBOM = "sbom"
_SCAN_TYPES = (CODE, SBOM)
_MODELS = {CODE: Scan, SBOM: SbomScan}


def _field(scan_type: str) -> str:
    if scan_type not in _SCAN_TYPES:
        raise ValueError(f"unknown trial scan_type: {scan_type!r}")
    return f"{scan_type}_scans_used"


def enabled() -> bool:
    return str(os.getenv("TRIAL_MODE", "")).strip().lower() == "true"


def limit() -> int:
    """The per-type cap -- code and SBOM each get this many, independently."""
    try:
        return int(os.getenv("TRIAL_SCAN_LIMIT", _DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT


def _row() -> TrialUsage:
    row = TrialUsage.objects.first()
    if row is None:
        row = TrialUsage.objects.create(updated_at=datetime.now(timezone.utc))
    return row


def used(scan_type: str) -> int:
    return getattr(_row(), _field(scan_type))


def in_progress(scan_type: str) -> int:
    """Scans of THIS type still holding a slot: currently running/queued, or
    interrupted (crashed, pending resume). Counted against that type's cap so
    a submission still in flight can't be double-counted by a concurrent
    request, and an interrupted scan can't be resumed past the limit either."""
    return _MODELS[scan_type].objects.filter(status__in=_ACTIVE_STATUSES).count()


def can_start(scan_type: str) -> bool:
    """True if a new scan of this type may begin (always True when trial mode
    is off). Code and SBOM are independent -- exhausting one never blocks the
    other."""
    if not enabled():
        return True
    return (used(scan_type) + in_progress(scan_type)) < limit()


def _model_path() -> Path:
    from django.conf import settings
    return Path(getattr(settings, "DATA_DIR", "")) / "model" / "astra.gguf"


def _delete_model_if_present() -> None:
    """Reclaim the bundled model's disk space (~4.68GB) once nothing on this
    install can use it anymore. Best-effort: never let cleanup failure break
    the scan response that triggered it.

    Also drops a TRIAL_EXHAUSTED marker beside it -- main.rs's asset-setup
    checks for this on every launch and skips model reassembly when present.
    Without it, the app would silently rebuild the model right back from its
    still-present bundled shards on the very next launch, undoing this
    entirely; deleting only the file, with nothing telling the app the
    deletion was intentional, would defeat the whole point.
    """
    try:
        path = _model_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.unlink()
        (path.parent / "TRIAL_EXHAUSTED").write_text(
            "code-scan trial exhausted; model intentionally removed", encoding="utf-8"
        )
    except Exception:
        pass


def record_completion(scan_type: str) -> None:
    """Increment this type's monotonic counter; no-op when trial mode is off.
    Called from each pipeline's completion step, so only successful scans of
    that type consume a slot.

    The bundled AI model is used ONLY by the code-scan verifier/enricher --
    SBOM scanning (grype/syft/cosign) is a purely deterministic pipeline and
    never touches it. So the moment the CODE trial allowance is exhausted,
    nothing on this install can use the model again (regardless of how many
    SBOM scans remain), and it's deleted to reclaim disk space. There's no
    re-fetch path for a deleted model -- it's reassembled once from bundled
    shards on first launch -- so this assumes "upgrade" always means a fresh
    delivery, never unlocking more scans on this same install.
    """
    if not enabled():
        return
    from django.db.models import F
    row = _row()
    field = _field(scan_type)
    TrialUsage.objects.filter(id=row.id).update(
        **{field: F(field) + 1}, updated_at=datetime.now(timezone.utc)
    )
    if scan_type == CODE and used(CODE) >= limit():
        _delete_model_if_present()


def status() -> dict:
    """UI/status payload. When trial mode is off, advertises an unlimited plan
    for both scan types. Otherwise each type reports its own limit/used/
    remaining, independent of the other."""
    if not enabled():
        empty = {"limit": None, "used": 0, "remaining": None}
        return {"trial_mode": False, "code": dict(empty), "sbom": dict(empty)}
    lim = limit()

    def _one(scan_type: str) -> dict:
        u = used(scan_type)
        return {"limit": lim, "used": u, "remaining": max(0, lim - u)}

    return {"trial_mode": True, "code": _one(CODE), "sbom": _one(SBOM)}

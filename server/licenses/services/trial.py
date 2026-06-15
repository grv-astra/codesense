"""Trial gate: cap the number of successfully-completed SAST scans.

Enabled only when ``TRIAL_MODE=true`` (off by default, so normal/production
deployments are unlimited). The count lives in a single monotonic ``TrialUsage``
row — independent of the (hard-deletable) Scan rows — so a client cannot reset
the trial by deleting scans. Enforcement is server-side; the UI count is UX.

Counting policy: a slot is consumed only on SUCCESSFUL completion
(``record_completion`` is called from the SAST pipeline's completion step, which
failed scans never reach). In-progress/queued scans are counted against the
limit at creation time so concurrent submissions can't overshoot the cap.
"""
import os
from datetime import datetime, timezone

from local.api_app.models.orm import Scan, TrialUsage

_ACTIVE_STATUSES = ("queued", "in_progress")
_DEFAULT_LIMIT = 2


def enabled() -> bool:
    return str(os.getenv("TRIAL_MODE", "")).strip().lower() == "true"


def limit() -> int:
    try:
        return int(os.getenv("TRIAL_SCAN_LIMIT", _DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT


def _row() -> TrialUsage:
    row = TrialUsage.objects.first()
    if row is None:
        row = TrialUsage.objects.create(scans_used=0, updated_at=datetime.now(timezone.utc))
    return row


def used() -> int:
    return _row().scans_used


def in_progress() -> int:
    """Currently running/queued SAST scans — counted against the cap so several
    concurrent submissions (the GitHub path allows >1) can't blow past it."""
    return Scan.objects.filter(status__in=_ACTIVE_STATUSES).count()


def can_start() -> bool:
    """True if a new SAST scan may begin (always True when trial mode is off)."""
    if not enabled():
        return True
    return (used() + in_progress()) < limit()


def record_completion() -> None:
    """Increment the monotonic counter; no-op when trial mode is off. Called from
    the SAST completion step, so only successful scans consume a slot."""
    if not enabled():
        return
    from django.db.models import F
    row = _row()
    TrialUsage.objects.filter(id=row.id).update(
        scans_used=F("scans_used") + 1, updated_at=datetime.now(timezone.utc)
    )


def status() -> dict:
    """UI/status payload. When trial mode is off, advertises an unlimited plan."""
    if not enabled():
        return {"trial_mode": False, "limit": None, "used": 0, "remaining": None}
    lim = limit()
    u = used()
    return {"trial_mode": True, "limit": lim, "used": u, "remaining": max(0, lim - u)}

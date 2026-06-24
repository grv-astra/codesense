"""Map a device tier to the GGUF filename the build stages.

The launcher/build chooses a tier for the target device (CPU/RAM headroom);
this keeps the tier→filename mapping and the MODEL_TIER env reading in one
tested place so the rest of the pipeline never hard-codes a model name.

Pure config — no model files are touched here. This is intentionally a no-op
for the current launch path (the Tauri shell and build scripts stage a fixed
``astra.gguf``); wiring a tier through to the staged filename is a deliberate
build-host step, not done automatically.
"""
from __future__ import annotations

import os

_TIERS = {
    "low": "astra-1.5B.gguf",
    "mid": "astra-7B.gguf",
    "high": "astra-14B.gguf",
}
_DEFAULT_TIER = "mid"


def gguf_filename_for_tier(tier: str | None) -> str:
    """Resolve a tier name to its GGUF filename, defaulting to the mid tier for
    unknown/empty input. Case- and whitespace-insensitive."""
    return _TIERS.get((tier or "").strip().lower(), _TIERS[_DEFAULT_TIER])


def model_tier() -> str:
    """The configured device tier from ``MODEL_TIER`` (low|mid|high), normalized.
    Unset or unrecognized values fall back to the mid tier. Read at call time so
    tests/env can toggle it."""
    tier = os.getenv("MODEL_TIER", "").strip().lower()
    return tier if tier in _TIERS else _DEFAULT_TIER

"""Read-only grace: when the license is expired or tampered, block writes/scans
but still allow reads (and the login/setup/license endpoints) so users can view
existing data and renew."""
from django.http import JsonResponse

from licenses.services import activation
from licenses.services.offline_license import get_state, EXPIRED, TAMPERED

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Always reachable even in read-only mode (auth + first-run setup + license
# status + activation). /api/activation matters here specifically: if a
# machine's registry already carries an EXPIRED license stamp from a prior
# build/delivery (HKCU\Software\CodeSense\license isn't scoped per-build) but
# activation hasn't happened yet on this install, activating would otherwise
# get rejected with a confusing "license expired" error before the user ever
# gets in.
_ALLOW_PREFIXES = ("/api/auth/login", "/api/auth/setup", "/api/license", "/api/activation", "/admin")


def _is_exempt(path: str) -> bool:
    # Segment-aware match so "/api/license" does not also exempt "/api/license-evil".
    return any(path == p or path.startswith(p + "/") for p in _ALLOW_PREFIXES)


class ReadOnlyGraceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if (
            request.method not in _SAFE_METHODS
            and path.startswith("/api/")
            and not _is_exempt(path)
        ):
            state = get_state()["state"]
            if state in (EXPIRED, TAMPERED):
                return JsonResponse(
                    {
                        "detail": "License expired or invalid — the app is in read-only mode.",
                        "license_state": state,
                    },
                    status=403,
                )
        return self.get_response(request)


class ActivationRequiredMiddleware:
    """Blocks every API route until this machine has redeemed the one-time
    activation password (see licenses.services.activation). No-op entirely
    when the build doesn't opt into the gate (no ACTIVATION_PASSWORD_HASH
    baked in) -- dev-from-source and ungated builds are unaffected.

    Runs ahead of ReadOnlyGraceMiddleware: an unactivated install can't even
    log in, let alone hit the read-only-vs-writable distinction.
    """
    _ALLOW_PREFIXES = ("/api/activation",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if (
            request.method != "OPTIONS"
            and path.startswith("/api/")
            and not any(path == p or path.startswith(p + "/") for p in self._ALLOW_PREFIXES)
            and not activation.is_activated()
        ):
            return JsonResponse(
                {"detail": "This app has not been activated yet.", "activated": False},
                status=403,
            )
        return self.get_response(request)

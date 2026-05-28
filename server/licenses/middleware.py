"""Read-only grace: when the license is expired or tampered, block writes/scans
but still allow reads (and the login/setup/license endpoints) so users can view
existing data and renew."""
from django.http import JsonResponse

from licenses.services.offline_license import get_state, EXPIRED, TAMPERED

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
# Always reachable even in read-only mode (auth + first-run setup + license status).
_ALLOW_PREFIXES = ("/api/auth/login", "/api/auth/setup", "/api/license", "/admin")


class ReadOnlyGraceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if (
            request.method not in _SAFE_METHODS
            and path.startswith("/api/")
            and not any(path.startswith(p) for p in _ALLOW_PREFIXES)
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

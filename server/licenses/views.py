from rest_framework.response import Response
from rest_framework.views import APIView

from licenses.services.offline_license import get_state
from licenses.services import trial


class LicenseStatusView(APIView):
    """GET /api/license/ — current offline license state for the UI banner."""

    def get(self, request):
        return Response(get_state())


class TrialStatusView(APIView):
    """GET /api/trial/ — trial-mode scan usage for the UI (trial_mode/limit/used/remaining)."""

    def get(self, request):
        return Response(trial.status())

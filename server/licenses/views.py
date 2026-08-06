from rest_framework.response import Response
from rest_framework.views import APIView

from licenses.services.offline_license import get_state
from licenses.services import activation, trial


class LicenseStatusView(APIView):
    """GET /api/license/ — current offline license state for the UI banner."""

    def get(self, request):
        return Response(get_state())


class TrialStatusView(APIView):
    """GET /api/trial/ — trial-mode scan usage for the UI (trial_mode/limit/used/remaining)."""

    def get(self, request):
        return Response(trial.status())


class ActivationView(APIView):
    """GET checks activation status; POST redeems the one-time password for
    this machine. See licenses.services.activation."""

    def get(self, request):
        return Response({
            "configured": activation.is_configured(),
            "activated": activation.is_activated(),
        })

    def post(self, request):
        password = request.data.get("password", "")
        if activation.activate(password):
            return Response({"activated": True})
        return Response(
            {"activated": False, "detail": "Incorrect activation password."},
            status=403,
        )

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from local.auth_app.services.setup import is_setup_needed, create_initial_admin


class SetupStatusView(APIView):
    def get(self, request):
        return Response({"setup_needed": is_setup_needed()}, status=status.HTTP_200_OK)


class SetupCreateAdminView(APIView):
    def post(self, request):
        if not is_setup_needed():
            return Response({"detail": "Setup already completed."}, status=status.HTTP_409_CONFLICT)
        email = (request.data.get("email") or "").strip()
        password = request.data.get("password") or ""
        name = (request.data.get("name") or "").strip()
        company = request.data.get("company")
        if not email or not password or not name:
            return Response({"detail": "email, password, and name are required."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            admin = create_initial_admin(email, password, name, company)
        except ValidationError as exc:
            detail = exc.detail[0] if isinstance(exc.detail, (list, tuple)) else exc.detail
            return Response({"detail": str(detail)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"user": admin}, status=status.HTTP_201_CREATED)

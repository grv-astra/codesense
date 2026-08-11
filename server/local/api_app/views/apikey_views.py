from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from local.auth_app.permissions.decorators import require_permission
from local.api_app.models.apikey_model import ApiKeyModel


def _serialize(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "key_prefix": row.key_prefix,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
    }


class ApiKeyListCreateView(APIView):
    @require_permission("update_project")
    def get(self, request, project_id):
        rows = ApiKeyModel.list_by_project(project_id)
        return Response([_serialize(r) for r in rows], status=status.HTTP_200_OK)

    @require_permission("update_project")
    def post(self, request, project_id):
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"error": "name is required"}, status=status.HTTP_400_BAD_REQUEST)

        created_by = request.user.get("id", "") if isinstance(request.user, dict) else ""
        row, plaintext_key = ApiKeyModel.create(project_id=project_id, name=name, created_by=created_by)
        data = _serialize(row)
        data["key"] = plaintext_key
        return Response(data, status=status.HTTP_201_CREATED)


class ApiKeyRevokeView(APIView):
    @require_permission("update_project")
    def post(self, request, project_id, key_id):
        row = ApiKeyModel.revoke(key_id, project_id)
        if not row:
            return Response({"error": "API key not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize(row), status=status.HTTP_200_OK)

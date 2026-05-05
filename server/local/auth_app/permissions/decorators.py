from rest_framework.response import Response
from rest_framework import status
from functools import wraps
from local.auth_app.utils.jwt import decode_token
from local.auth_app.models.permission_model import PermissionModel
from local.auth_app.utils.account_integrity import verify_payload_user

def require_role(*allowed_roles):
    def decorator(view_method):
        @wraps(view_method)
        def _wrapped_view(self, request, *args, **kwargs):  # Use `self` not `view`
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
            
            token = auth_header.split(" ")[1]
            payload = decode_token(token)
            if not payload:
                return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

            integrity_issue = verify_payload_user(payload)
            if integrity_issue:
                return Response(integrity_issue, status=status.HTTP_401_UNAUTHORIZED)

            role = payload.get("role", "").lower()
            if role not in [r.lower() for r in allowed_roles]:
                return Response({"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN)
            
            request.user = payload  # Attach user to request
            return view_method(self, request, *args, **kwargs)  # self = view class instance

        return _wrapped_view
    return decorator


def require_authentication():
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
            
            token = auth_header.split(" ")[1]
            payload = decode_token(token)
            if not payload:
                return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

            integrity_issue = verify_payload_user(payload)
            if integrity_issue:
                return Response(integrity_issue, status=status.HTTP_401_UNAUTHORIZED)
            
            request.user = payload
            return view_func(view, request, *args, **kwargs)
        return _wrapped_view
    return decorator

def require_permission(permission_key):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view, request, *args, **kwargs):
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)
            
            token = auth_header.split(" ")[1]
            payload = decode_token(token)
            if not payload:
                return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

            integrity_issue = verify_payload_user(payload)
            if integrity_issue:
                return Response(integrity_issue, status=status.HTTP_401_UNAUTHORIZED)

            role = payload.get("role")
            
            permissions = PermissionModel.get_permissions_for_role(role)
            if not permissions.get(permission_key):
                return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
            
            request.user = payload
            return view_func(view, request, *args, **kwargs)
        return _wrapped_view
    return decorator

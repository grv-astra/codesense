from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from local.auth_app.serializers.user_serializer import LoginSerializer
from local.auth_app.models.user_model import UserModel
from local.auth_app.models.permission_model import PermissionModel
from local.auth_app.utils.password import verify_password
from local.auth_app.utils.jwt import generate_token
from local.auth_app.utils.account_integrity import verify_user
from local.auth_app.permissions.decorators import require_role, require_authentication

class GetPermissionsView(APIView):
    @require_authentication()
    def get(self, request, role):
        permissions = PermissionModel.get_permissions_for_role(role)
        return Response({"role": role, "permissions": permissions}, status=status.HTTP_200_OK)

class GetMyPermissionsView(APIView):
    @require_authentication()
    def get(self, request):
        user = request.user
        role = user.get("role", "admin")
        permissions = PermissionModel.get_permissions_for_role(role)
        return Response({"role": role, "permissions": permissions}, status=status.HTTP_200_OK)

class SetPermissionsView(APIView):
    @require_role("Admin")
    def post(self, request):
        role = request.data.get("role")
        permissions = request.data.get("permissions")

        if not role or not isinstance(permissions, dict):
            return Response({"detail": "Role and permissions dictionary required."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate permissions
        valid_keys = set(PermissionModel.get_all_permission_keys())
        for key in permissions:
            if key not in valid_keys:
                return Response({"detail": f"Invalid permission key: {key}"}, status=status.HTTP_400_BAD_REQUEST)

        PermissionModel.set_permissions_for_role(role, permissions)
        permissions = PermissionModel.get_permissions_for_role(role)
        return Response({"detail": f"Permissions set for role: {role}", "role": role, "permissions": permissions }, status=status.HTTP_200_OK)


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        email = data["email"].strip()

        user = UserModel.find_by_email(email)

        if not user:
            return Response({"detail": "User doesn't exist, please use registered email"}, status=status.HTTP_404_NOT_FOUND)

        integrity_issue = verify_user(user)
        if integrity_issue:
            return Response(integrity_issue, status=status.HTTP_401_UNAUTHORIZED)

        if not verify_password(data["password"], user["password"]):
            return Response({"detail": "Incorrect password, please use vaild credentials"}, status=status.HTTP_400_BAD_REQUEST)

        searlized_user = UserModel.serialize_user(user=user)
        token = generate_token({
            "id": str(user["_id"]),
            "role": user["role"],
            "email": user.get("email"),
            "name": user.get("name"),
        })
        return Response({
            "token": token, "user": searlized_user
        }, 
        status=status.HTTP_200_OK)

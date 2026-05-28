from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
 
from local.auth_app.serializers.user_serializer import RegisterUserSerializer, UpdateUserSerializer
from local.auth_app.models.user_model import UserModel
from local.auth_app.permissions.decorators import require_role, require_authentication
from local.auth_app.utils.password import hash_password, validate_strong_password
from local.auth_app.utils.account_integrity import register_user
 
from licenses.services.auth import require_assertion_jwt

class ProfileView(APIView):
    @require_authentication()
    def get(self, request):
        user = request.user
        user_id = user.get("id", "")
       
        if not user_id:
            return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
 
        user = UserModel.find_by_id(user_id)
        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
 
        return Response(user , status=status.HTTP_200_OK)
 
class FetchUserDetails(APIView):
    @require_role("Admin", "Manager")
    def get(self, request, user_id):
        if not user_id:
            return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
 
        user = UserModel.find_by_id(user_id)
        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
 
        return Response(user , status=status.HTTP_200_OK)
 
class UserModuleView(APIView):
    @require_role("Admin")
    # @require_assertion_jwt("user", force_refresh=True)
    def post(self, request):
        serializer = RegisterUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        if UserModel.find_by_email(data["email"]):
            return Response({"detail": "Email already registered"}, status=status.HTTP_400_BAD_REQUEST)

        # strong password validation
        try:
            validate_strong_password(data["password"])
        except ValidationError as e:
            # e.detail is usually a list or dict of ErrorDetail objects
            if isinstance(e.detail, (list, tuple)):
                message = str(e.detail[0])
            elif isinstance(e.detail, dict):
                # pick first field error
                first_key = next(iter(e.detail))
                message = str(e.detail[first_key][0])
            else:
                message = str(e.detail)

            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)


        user = UserModel.create_user(
            email=data["email"],
            hashed_password=hash_password(data["password"]),
            name=data["name"],
            company=data["company"],
            role=data["role"],
        )
        creator_email = (request.user or {}).get("email") or "admin"
        db_user = UserModel.find_by_email(data["email"])
        if db_user:
            register_user(db_user, created_by=creator_email)
        return Response(user, status=status.HTTP_201_CREATED)

   
    @require_role("Admin", "Manager")
    def patch(self, request, user_id):
        serializer = UpdateUserSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
       
        if not UserModel.find_by_id(user_id=user_id):
            return Response({"detail": "User doesn't exist, please use registered email"}, status=status.HTTP_404_NOT_FOUND)
 
        data = serializer.validated_data
        if "password" in data:
            data["password"] = hash_password(data.get("password"))
        
        user = UserModel.update_user(
            user_id=user_id,
            update_data=data
        )
        db_user = UserModel.find_by_email(user["email"]) if user else None
        if db_user:
            register_user(db_user, created_by=(request.user or {}).get("email") or "admin")
        return Response(user, status=status.HTTP_202_ACCEPTED)
   
    @require_role("Admin", "Manager")
    def delete(self, request, user_id):
        if not UserModel.find_by_id(user_id=user_id):
            return Response({"detail": "User doesn't exist, please use valid user_id"}, status=status.HTTP_404_NOT_FOUND)
 
        existing_user = UserModel.find_raw_by_id(user_id)
        UserModel.update_user(
            user_id=user_id,
            update_data={"deleted": True}
        )
        if existing_user:
            existing_user["deleted"] = True
            register_user(existing_user, created_by=(request.user or {}).get("email") or "admin")
        return Response({ "detail": "User deleted successfully" }, status=status.HTTP_202_ACCEPTED)
   
    @require_role("Admin", "Manager")
    def get(self, request):
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 10))
 
        user = request.user
        user_role = user.get("role", "").lower()

        if user_role == "manager":
            all_users = UserModel.find_all(page=page, limit=limit, role="manager")
        else:
            all_users = UserModel.find_all(page=page, limit=limit, role="admin")
        return Response(all_users, status=status.HTTP_200_OK)

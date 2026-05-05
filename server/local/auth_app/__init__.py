from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from local.auth_app.utils.jwt import decode_token
from local.auth_app.utils.django_user_proxy import AuthenticatedUser, AnonymousUser

class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None  # DRF will treat as anonymous
        token = auth_header.split(" ")[1]
        payload = decode_token(token)
        if not payload:
            raise AuthenticationFailed("Invalid or expired token") 
        return (AuthenticatedUser(payload), None)
from django.urls import path, include
from ..views.auth_views import LoginView
from ..views.user_views import ProfileView, UserModuleView

urlpatterns = [
    path('register/', UserModuleView.as_view(), name="create_user"),
    path('login/', LoginView.as_view(), name="login"),
    path('me/', ProfileView.as_view(), name="user_profile"),
    path('users/', include("local.auth_app.urls.users_urls")),
    path('permissions/', include("local.auth_app.urls.permissions_urls")),
]

from django.urls import path
from ..views.auth_views import SetPermissionsView, GetMyPermissionsView, GetPermissionsView

urlpatterns = [
    path('update/', SetPermissionsView.as_view(), name="update_permissions"),
    path('me/', GetMyPermissionsView.as_view(), name="my_permissions"),
    path('<str:role>/', GetPermissionsView.as_view(), name="fetch_permissions"),
]

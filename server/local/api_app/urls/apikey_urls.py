from django.urls import path
from ..views.apikey_views import ApiKeyListCreateView, ApiKeyRevokeView

urlpatterns = [
    path('', ApiKeyListCreateView.as_view(), name='apikey-list-create'),
    path('<str:key_id>/revoke/', ApiKeyRevokeView.as_view(), name='apikey-revoke'),
]

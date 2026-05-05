from django.urls import path, include
from ..views.user_views import UserModuleView, FetchUserDetails

urlpatterns = [
    path('', UserModuleView.as_view(), name="all_users"),
    path('update/<str:user_id>/', UserModuleView.as_view(), name="update_user"),
    path('delete/<str:user_id>/', UserModuleView.as_view(), name="delete_user"),
    path('<str:user_id>/', FetchUserDetails.as_view(), name="get_user"),
]

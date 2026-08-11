from django.urls import path, include
from ..views.dashboard_views import DashboardView
urlpatterns = [
    path('projects/', include('local.api_app.urls.project_urls')),
    path('projects/<str:project_id>/api-keys/', include('local.api_app.urls.apikey_urls')),
    path('scans/', include('local.api_app.urls.scan_urls')),
    path('findings/', include('local.api_app.urls.finding_urls')),
    path('dashboard/', DashboardView.as_view())
]

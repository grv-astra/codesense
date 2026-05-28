from django.urls import path
from ..views.scan_views import ScanCreateView, ScanDetailView, ScanListView, GitHubRepoScanView, SbomCreateView, SbomScanDetailView, GrypeCreateView
 
urlpatterns = [
    path("create/", ScanCreateView.as_view(), name="create-scan"),
    path("github/", GitHubRepoScanView.as_view(), name="git-clone-scan"),
 
    path("<str:scan_id>/", ScanDetailView.as_view(), name="scan-detail"),
    path("delete/<str:scan_id>/", ScanDetailView.as_view(), name="scan-delete"),

    # shared
    path("project/<str:project_id>/", ScanListView.as_view(), name="scan-list"),

    path("sbom/create/", SbomCreateView.as_view(), name="create-sbom-scan"),
    path("grype/create/", GrypeCreateView.as_view(), name="create-grype-scan"),
    path("sbom/<str:scan_id>/", SbomScanDetailView.as_view(), name="scan-detail"),
    path("sbom/delete/<str:scan_id>/", SbomScanDetailView.as_view(), name="scan-delete"),
]
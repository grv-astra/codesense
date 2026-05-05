# projects/urls.py
from django.urls import path
from ..views.finding_views import FindingDetailView, FindingListCreateView, ExportFindingView, ExportSbomFindingView, SbomFindingListCreateView, SbomLicenseFindingList

urlpatterns = [
    path('scan/csv/<str:scan_id>/', ExportFindingView.as_view(), name="export_findings_by_scan"),
    path('scan/sbom/csv/<str:scan_id>/', ExportSbomFindingView.as_view(), name="export_sbom_findings_by_scan"),
    path('scan/<str:scan_id>/', FindingListCreateView.as_view(), name="findings_by_scan"),
    path('scan/sbom/<str:scan_id>/', SbomFindingListCreateView.as_view(), name="findings_by_scan"),
    path('sbom/licenses/<str:scan_id>/', SbomLicenseFindingList.as_view(), name="license_findings_by_scan"),
    path('approve/<str:finding_id>/', FindingDetailView.as_view(), name="approve_finding"),
    path('delete/<str:finding_id>/', FindingDetailView.as_view(), name="delete_finding"),
    path('<str:finding_id>/', FindingDetailView.as_view(), name="finding_by_id"),
]

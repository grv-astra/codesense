from django.urls import path
from scanner.views import ScanCreateView, ScanProgressView, TestScanView

urlpatterns = [
    path("test/", TestScanView.as_view(), name="test-scan"),
    path("create/", ScanCreateView.as_view(), name="create-scan"),
    path("<str:scan_id>/", ScanProgressView.as_view(), name="scan-detail"),
    
]

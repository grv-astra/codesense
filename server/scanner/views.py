import os, zipfile, uuid
import tempfile
from django.db import close_old_connections
from django.http import JsonResponse
from django.conf import settings
from local.api_app.models.scan_models import ScanModel
from local.api_app.serializers.scan_serializers import ScanStartSerializer
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework import status
from .rag.scanner import scan_folder
import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
import time
 
# Global tracking for concurrent scans
active_scans = {}
scan_counter = 0
scan_lock = threading.Lock()
MAX_CONCURRENT_SCANS = 10
 
MEDIA_ROOT = os.path.join(settings.BASE_DIR, "media", "scans")
os.makedirs(MEDIA_ROOT, exist_ok=True)
 
@method_decorator(csrf_exempt, name='dispatch')
class ScanCreateView(APIView):
    def post(self, request):
        serializer = ScanStartSerializer(data=request.data)
        if serializer.is_valid():
            scan_name = serializer.validated_data['scan_name']
            project_id = serializer.validated_data['project_id']
            triggered_by = serializer.validated_data.get('triggered_by', '')
            zip_file = serializer.validated_data['zip_file']
 
            # Check concurrent scan limit
            with scan_lock:
                current_active = len([s for s in active_scans.values() if s.is_alive()])
                if current_active >= MAX_CONCURRENT_SCANS:
                    return JsonResponse({
                        "detail": f"Maximum concurrent scans ({MAX_CONCURRENT_SCANS}) reached. Please try again later."
                    }, status=status.HTTP_429_TOO_MANY_REQUESTS)
 
            # Create scan doc
            scan_data = {
                "scan_name": scan_name,
                "project_id": project_id,
                "status": "queued",
                "triggered_by": triggered_by if triggered_by else None
            }
            scan = ScanModel.create(scan_data)
            scan_id = scan["id"]
 
            # Create temporary directory for both ZIP file and extraction
            temp_dir = tempfile.mkdtemp()
            temp_zip_path = os.path.join(temp_dir, zip_file.name)
            extracted_folder_path = os.path.join(temp_dir, 'extracted')
   
            try:
                # Save uploaded ZIP file
                with open(temp_zip_path, 'wb+') as f:
                    for chunk in zip_file.chunks():
                        f.write(chunk)
                logging.info(f"Uploaded zipped folder saved to {temp_zip_path}")
 
                os.makedirs(extracted_folder_path, exist_ok=True)
                with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extracted_folder_path)
                logging.info(f"ZIP file extracted to {extracted_folder_path}")
               
                # List contents for debugging
                extracted_contents = []
                for root, dirs, files in os.walk(extracted_folder_path):
                    for file in files:
                        extracted_contents.append(os.path.join(root, file))
                logging.info(f"Extracted {len(extracted_contents)} files: {extracted_contents[:10]}...")  # Show first 10 files
 
            except zipfile.BadZipFile:
                logging.error("Uploaded file is not a valid ZIP file")
                shutil.rmtree(temp_dir)
                return JsonResponse({"error": "Invalid zip file"}, status=status.HTTP_400_BAD_REQUEST)
 
            except Exception as e:
                logging.error(f"Failed to process uploaded file: {e}")
                shutil.rmtree(temp_dir)
                return JsonResponse({"detail": "Failed to process uploaded file."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
           
            # Start scan in background thread
            def run_scan():
                try:
                    logging.info(f"Starting concurrent scan with scan_name={scan_name}")
                   
                    # Call scan_folder with extracted folder path
                    findings = scan_folder(
                        folder_path=extracted_folder_path,
                        scan_id=scan_id,
                        triggered_by=triggered_by,
                        scan_name=scan_name,
                    )
                    logging.info(f"Concurrent scan completed successfully. Found {len(findings) if findings else 0} vulnerabilities.")
                   
                except Exception as e:
                    logging.error(f"Error during concurrent scan: {e}")
                    import traceback
                    logging.error(traceback.format_exc())
                finally:
                    # Cleanup temp files and directory
                    try:
                        shutil.rmtree(temp_dir)
                        logging.info(f"Cleaned up temporary directory: {temp_dir}")
                    except Exception as e:
                        logging.error(f"Error cleaning up temporary files: {e}")
                    finally:
                        # Remove from active scans
                        with scan_lock:
                            active_scans.pop(scan_id, None)
                        # This thread never goes through Django's request_started/
                        # request_finished signals, so its DB connection is never
                        # auto-closed -- release it explicitly or it lingers open
                        # for the life of the (GC-eligible) thread object.
                        close_old_connections()
 
            # Start the scan in a new thread
            scan_thread = threading.Thread(target=run_scan, daemon=True)
            with scan_lock:
                active_scans[scan_id] = scan_thread
            scan_thread.start()
 
            return JsonResponse({"detail": "Scan started successfully.", "scan": scan}, status=status.HTTP_202_ACCEPTED)
        else:
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
   
class ScanProgressView(APIView):
    def get(self, request, scan_id):
        scan = ScanModel.find_by_id(scan_id=scan_id)
        if not scan:
            return JsonResponse({"error": "Scan not found"}, status=404)

        return JsonResponse({"result": scan })
 
       
class TestScanView(APIView):
    def get(self, request):
        return JsonResponse({"detail": "Hello"})
 

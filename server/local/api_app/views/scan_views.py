import os, zipfile, uuid
import tempfile
from django.http import JsonResponse
from django.conf import settings
from local.api_app.models.scan_models import ScanModel
from local.api_app.serializers.scan_serializers import ScanStartSerializer
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework import status
from scanner.rag.scanner import scan_folder
import logging
import shutil
import threading
 
from local.auth_app.permissions.decorators import require_permission
from licenses.services.auth import require_assertion_jwt
from rest_framework.response import Response
import asyncio
from scanner.services.scan_service import scan_github_repo
from scanner.rag.llm import get_llm
from scanner.rag.progress import update_progress
from datetime import datetime, timezone
from local.api_app.models.sbom_models import SbomModel
from local.api_app.serializers.scan_serializers import ScanStartSerializer, ScanWithSbomSerializer
 
scan_thread = None
scan_thread_lock = threading.Lock()
# Global scan controls
scan_lock = threading.Lock()
active_scans = {}
MAX_CONCURRENT_SCANS = 5
 
 
MEDIA_ROOT = os.path.join(settings.BASE_DIR, "media", "scans")
os.makedirs(MEDIA_ROOT, exist_ok=True)
 
@method_decorator(csrf_exempt, name='dispatch')
class ScanCreateView(APIView):
    @require_permission("create_scan")
    # @require_assertion_jwt("scan", force_refresh=True)
    def post(self, request):
        serializer = ScanStartSerializer(data=request.data)
        user = request.user
        triggered_by = user.get("id", "68863cf8ee93d4964a00d585")
 
        if serializer.is_valid():
            scan_name = serializer.validated_data['scan_name']
            project_id = serializer.validated_data['project_id']
            zip_file = serializer.validated_data['zip_file']
 
            # Create scan doc
            scan_data = {
                "scan_name": scan_name,
                "project_id": project_id,
                "status": "queued",
                "source": "zip",
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
                    logging.info(f"Starting scan with scan_name={scan_name}")
                   
                    # Call scan_folder with extracted folder path
                    findings = scan_folder(
                        folder_path=extracted_folder_path,
                        scan_id=scan_id,
                        triggered_by=triggered_by,
                        scan_name=scan_name,
                    )
                    logging.info(f"Scan completed successfully. Found {len(findings) if findings else 0} vulnerabilities.")
                   
                except Exception as e:
                    logging.error(f"Error during scan: {e}")
                    ScanModel.update_status(scan_id, "failed")
                    update_progress(
                        scan_id=scan_id,
                        status="failed",
                        end_time=datetime.now(timezone.utc),
                        error=str(e),
                    )
                    import traceback
                    logging.error(traceback.format_exc())
                finally:
                    # Cleanup temp files and directory
                    try:
                        shutil.rmtree(temp_dir)
                        logging.info(f"Cleaned up temporary directory: {temp_dir}")
                    except Exception as e:
                        logging.error(f"Error cleaning up temporary files: {e}")
 
            global scan_thread
            with scan_thread_lock:
                if scan_thread and scan_thread.is_alive():
                    return JsonResponse({"detail": "Scan already in progress."}, status=status.HTTP_409_CONFLICT)
                scan_thread = threading.Thread(target=run_scan, daemon=True)
                scan_thread.start()
 
            return JsonResponse({"detail": "Scan started successfully.", "scan": scan}, status=status.HTTP_202_ACCEPTED)
        else:
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
   
   
class ScanDetailView(APIView):
    @require_permission("view_scans")
    def get(self, request, scan_id):
        scan = ScanModel.find_by_id(scan_id=scan_id)
        if not scan:
            return JsonResponse({"error": "Scan not found"}, status=status.HTTP_404_NOT_FOUND)
 
        return JsonResponse(scan, status=status.HTTP_200_OK)
   
    @require_permission("delete_scan")
    def delete(self, request, scan_id):
        res = ScanModel.delete_scan(scan_id=scan_id)
        if not res:
            return JsonResponse({"error": "Scan not found"}, status=status.HTTP_404_NOT_FOUND)
        return JsonResponse({"detail": "Scan deleted permenantly"}, status=status.HTTP_204_NO_CONTENT)
   
       
class ScanListView(APIView):
    @require_permission("view_scans")
    def get(self, request, project_id):
        type = str(request.query_params.get("type", "sca"))
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 10))
    
        scans = []
        match type:
            case "sca":
                scans = ScanModel.find_by_project(project_id=project_id, page=page, limit=limit)
            case "sbom":
                scans = SbomModel.find_by_project(project_id=project_id, page=page, limit=limit)
        
        if not scans:
            return JsonResponse({"error": "scan not found"}, status=status.HTTP_404_NOT_FOUND)
 
        return JsonResponse(scans, status=status.HTTP_200_OK)
 
 
class GitHubRepoScanView(APIView):
    @require_permission("create_scan")
    # @require_assertion_jwt("scan", force_refresh=True)
    def post(self, request):
        token = request.data.get("token") or request.data.get("git_token")
        username = request.data.get("username") or request.data.get("git_rowner")
        repo = request.data.get("repo") or request.data.get("git_repo")
        branch = request.data.get("branch", "main")
        scan_name = request.data.get("scan_name", f"{repo}-{branch}")
        project_id = request.data.get("project_id")
        triggered_by = request.data.get("triggered_by")
        if not triggered_by and hasattr(request, "user") and isinstance(request.user, dict):
            triggered_by = request.user.get("id")
 
        if not all([token, username, repo, project_id]):
            return Response(
                {"error": "token, username, repo, project_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
 
        # Prevent too many concurrent scans
        with scan_lock:
            current_active = len([s for s in active_scans.values() if s.is_alive()])
            if current_active >= MAX_CONCURRENT_SCANS:
                return Response(
                    {"detail": f"Max concurrent scans ({MAX_CONCURRENT_SCANS}) reached"},
                    status=429
                )
 
        # DB log
        scan = ScanModel.create({
            "scan_name": scan_name,
            "project_id": project_id,
            "status": "queued",
            "source": "github",
            "triggered_by": triggered_by or None,
        })
        scan_id = scan["id"]
 
        # Background thread
        def run_github_scan():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
 
                # Download repo → return folder_path
                result = loop.run_until_complete(
                    scan_github_repo(token, username, repo, branch)
                )
 
                folder_path = result["folder_path"]
 
                scan_folder(
                    folder_path=folder_path,
                    scan_id=scan_id,
                    triggered_by=triggered_by,
                    scan_name=scan_name
                )
 
            except Exception as e:
                logging.error(f"GitHub scan failed: {e}")
                ScanModel.update_status(scan_id, "failed")
                update_progress(
                    scan_id=scan_id,
                    status="failed",
                    end_time=datetime.now(timezone.utc),
                    error=str(e),
                )
 
            finally:
                with scan_lock:
                    active_scans.pop(scan_id, None)
 
        t = threading.Thread(target=run_github_scan, daemon=True)
        with scan_lock:
            active_scans[scan_id] = t
        t.start()
 
        return Response(
            {"detail": "GitHub scan started", "scan": scan},
            status=202
        )


class ModelHealthView(APIView):
    @require_permission("view_scans")
    def get(self, request):
        client = get_llm()
        try:
            health = client.healthcheck()
            return Response(
                {
                    "status": "ok",
                    "provider": "vllm",
                    "base_url": health["base_url"],
                    "configured_model": health["configured_model"],
                    "available_models": health["available_models"],
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response(
                {
                    "status": "error",
                    "provider": "vllm",
                    "configured_model": client.model,
                    "base_url": client.base_url,
                    "error": str(exc),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

@method_decorator(csrf_exempt, name="dispatch")
class SbomCreateView(APIView):

    @require_permission("create_scan")
    # @require_assertion_jwt("scan", force_refresh=True)
    def post(self, request):

        serializer = ScanStartSerializer(data=request.data)
        user = request.user
        triggered_by = user.get("id", "68863cf8ee93d4964a00d585")

        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        scan_name = serializer.validated_data["scan_name"]
        project_id = serializer.validated_data["project_id"]
        zip_file = serializer.validated_data["zip_file"]

        scan_data = {
            "scan_name": scan_name,
            "project_id": project_id,
            "status": "queued",
            "triggered_by": triggered_by if triggered_by else None,
        }

        scan = SbomModel.create(scan_data)
        scan_id = scan["id"]

        logging.info(f"Created SBOM scan {scan_id}")

        temp_dir = tempfile.mkdtemp()
        temp_zip_path = os.path.join(temp_dir, zip_file.name)
        extracted_folder_path = os.path.join(temp_dir, "extracted")

        try:

            with open(temp_zip_path, "wb+") as f:
                for chunk in zip_file.chunks():
                    f.write(chunk)
            os.makedirs(extracted_folder_path, exist_ok=True)

            with zipfile.ZipFile(temp_zip_path, "r") as zip_ref:
                # Prevent Zip Slip
                for member in zip_ref.namelist():
                    member_path = os.path.abspath(
                        os.path.join(extracted_folder_path, member)
                    )
                    if not member_path.startswith(os.path.abspath(extracted_folder_path)):
                        raise Exception("Zip Slip attack detected")

                zip_ref.extractall(extracted_folder_path)
        except zipfile.BadZipFile:
            shutil.rmtree(temp_dir)
            return JsonResponse(
                {"error": "Invalid zip file"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            logging.error(f"Zip processing failed: {e}")
            shutil.rmtree(temp_dir)
            return JsonResponse(
                {"detail": "Failed to process uploaded file."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # --------------------------------
        # Background scan worker
        # --------------------------------

        def run_scan():
            try:
                logging.info(f"Starting SBOM scan {scan_id}")
                SbomModel.update_status(scan_id, "in_progress")
                from scanner.services.sbom_pipeline import run_project_pipeline
                results = run_project_pipeline(
                    project_path=extracted_folder_path,
                    scan_id=scan_id,
                    triggered_by=triggered_by,
                )

                SbomModel.update_progress(
                    scan_id,
                    vulnerabilities=results["total_vulnerabilities"],
                    severity_counts=results["severity_counts"],
                    ecosystems=results["ecosystems"],
                    dependencies_scanned=results["dependencies_scanned"],
                    status="completed",
                    end_time=datetime.now(timezone.utc),
                )

                logging.info(
                    f"SBOM scan {scan_id} completed. "
                    f"{results['total_vulnerabilities']} vulnerabilities found"
                )

            except Exception as e:
                logging.error(f"SBOM scan {scan_id} failed: {e}")
                SbomModel.update_status(scan_id, "failed")

            finally:
                # cleanup temporary project extraction
                try:
                    shutil.rmtree(temp_dir)
                    logging.info(f"Cleaned workspace for scan {scan_id}")
                except Exception as e:
                    logging.error(f"Cleanup failed for scan {scan_id}: {e}")

        global scan_thread
        with scan_thread_lock:
            if scan_thread and scan_thread.is_alive():
                return JsonResponse(
                    {"detail": "Another scan already in progress."},
                    status=status.HTTP_409_CONFLICT,
                )

            scan_thread = threading.Thread(
                target=run_scan,
                daemon=True
            )

            scan_thread.start()

        return JsonResponse(
            {
                "detail": "SBOM scan started successfully.",
                "scan": scan
            },
            status=status.HTTP_202_ACCEPTED,
        )

   


@method_decorator(csrf_exempt, name="dispatch")
class GrypeCreateView(APIView):

    @require_permission("create_scan")
    # @require_assertion_jwt("scan", force_refresh=True)
    def post(self, request):

        serializer = ScanWithSbomSerializer(data=request.data)
        user = request.user
        triggered_by = user.get("id", None)

        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        scan_name = serializer.validated_data["scan_name"]
        project_id = serializer.validated_data["project_id"]
        sbom_file = serializer.validated_data["sbom_file"]

        # 🔴 Basic validation
        if not sbom_file.name.endswith((".json", ".xml")):
            return JsonResponse(
                {"error": "Only JSON or XML SBOM files are supported"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scan_data = {
            "scan_name": scan_name,
            "project_id": project_id,
            "status": "queued",
            "triggered_by": triggered_by,
        }

        scan = SbomModel.create(scan_data)
        scan_id = scan["id"]

        logging.info(f"Created SBOM scan {scan_id}")

        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, sbom_file.name)

        try:
            # Save SBOM file
            with open(temp_file_path, "wb+") as f:
                for chunk in sbom_file.chunks():
                    f.write(chunk)

        except Exception as e:
            logging.error(f"Failed to save SBOM file: {e}")
            shutil.rmtree(temp_dir)
            return JsonResponse(
                {"detail": "Failed to process uploaded file."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # --------------------------------
        # Background scan worker
        # --------------------------------

        def run_scan():
            try:
                logging.info(f"Starting SBOM scan {scan_id}")
                SbomModel.update_status(scan_id, "in_progress")

                from scanner.services.sbom_pipeline import run_sbom_pipeline

                print(f"Running SBOM pipeline with file: {temp_file_path}")
                results = run_sbom_pipeline(
                    sbom_path=temp_file_path,   # 🔴 changed
                    scan_id=scan_id,
                    triggered_by=triggered_by,
                )

                SbomModel.update_progress(
                    scan_id,
                    vulnerabilities=results["total_vulnerabilities"],
                    severity_counts=results["severity_counts"],
                    ecosystems=results["ecosystems"],
                    dependencies_scanned=results["dependencies_scanned"],
                    status="completed",
                    end_time=datetime.now(timezone.utc),
                )

                logging.info(
                    f"SBOM scan {scan_id} completed. "
                    f"{results['total_vulnerabilities']} vulnerabilities found"
                )

            except Exception as e:
                logging.error(f"SBOM scan {scan_id} failed: {e}")
                SbomModel.update_status(scan_id, "failed")

            finally:
                try:
                    shutil.rmtree(temp_dir)
                    logging.info(f"Cleaned workspace for scan {scan_id}")
                except Exception as e:
                    logging.error(f"Cleanup failed for scan {scan_id}: {e}")

        global scan_thread
        with scan_thread_lock:
            if scan_thread and scan_thread.is_alive():
                return JsonResponse(
                    {"detail": "Another scan already in progress."},
                    status=status.HTTP_409_CONFLICT,
                )

            scan_thread = threading.Thread(target=run_scan, daemon=True)
            scan_thread.start()

        return JsonResponse(
            {
                "detail": "SBOM scan started successfully.",
                "scan": scan
            },
            status=status.HTTP_202_ACCEPTED,
        )


class SbomScanDetailView(APIView):
    @require_permission("view_scans")
    def get(self, request, scan_id):
        scan = SbomModel.find_by_id(scan_id=scan_id)
        if not scan:
            return JsonResponse({"error": "Scan not found"}, status=status.HTTP_404_NOT_FOUND)
 
        return JsonResponse(scan, status=status.HTTP_200_OK)
   
    @require_permission("delete_scan")
    def delete(self, request, scan_id):
        res = SbomModel.delete_scan(scan_id=scan_id)
        if not res:
            return JsonResponse({"error": "Scan not found"}, status=status.HTTP_404_NOT_FOUND)
        return JsonResponse({"detail": "Scan deleted permenantly"}, status=status.HTTP_204_NO_CONTENT)  

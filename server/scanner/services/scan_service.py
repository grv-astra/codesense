import os
import zipfile
import uuid
from django.conf import settings
from scanner.utils.github_downloader import download_github_repo_zip
 
 
async def scan_github_repo(token, username, repo, branch):
    scan_id = str(uuid.uuid4())
 
    base_dir = os.path.join(settings.BASE_DIR, "media", "scans")
    os.makedirs(base_dir, exist_ok=True)
 
    zip_path = os.path.join(base_dir, f"{scan_id}.zip")
    extract_path = os.path.join(base_dir, scan_id)
    os.makedirs(extract_path, exist_ok=True)
 
    zip_bytes = await download_github_repo_zip(token, username, repo, branch)
 
    with open(zip_path, "wb") as f:
        f.write(zip_bytes.read())
 
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_path)
 
    return {
        "folder_path": extract_path
    }
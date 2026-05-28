# PyInstaller spec for the Code Sense backend sidecar.
#
# Build on the TARGET OS (Windows for the desktop app):
#   pip install -r requirements.txt pyinstaller
#   pyinstaller codesense.spec
# Produces dist/codesense-server(.exe). Rename with Tauri's target-triple suffix
#   codesense-server-x86_64-pc-windows-msvc.exe
# and drop into client/src-tauri/binaries/ (see client/src-tauri/README.md).
#
# SCAFFOLD: not built in the CI sandbox (PyInstaller here would yield a macOS/Linux
# binary, not Windows). Validate on the Windows build host; Django's dynamic app
# loading occasionally needs an extra hiddenimport — add as the build surfaces them.
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

_APPS = [
    "django", "rest_framework", "corsheaders", "codesense",
    "local", "local.auth_app", "local.api_app", "scanner", "licenses", "common",
]

hiddenimports = []
for pkg in _APPS:
    hiddenimports += collect_submodules(pkg)

datas = collect_data_files("rest_framework")

a = Analysis(
    ["run_server.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pymongo", "bson", "langchain", "langchain_community", "faiss", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="codesense-server",
    console=True,
    onefile=True,
    upx=False,
)

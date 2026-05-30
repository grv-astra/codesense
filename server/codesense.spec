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
import os

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

_APPS = [
    "django", "rest_framework", "corsheaders", "codesense",
    "local", "local.auth_app", "local.api_app", "scanner", "licenses", "common",
]

hiddenimports = []
for pkg in _APPS:
    hiddenimports += collect_submodules(pkg)

# The local apps expose routes as urls/ PACKAGES whose __init__ include()s DRF
# sub-urlconfs by string (e.g. local.api_app.urls.scan_urls). Those submodules read
# Django settings at import time, so collect_submodules (which imports each module
# in an isolated subprocess with no configured Django) skips them, and PyInstaller
# never follows the string include()s. Enumerate every .py in those url packages
# from disk (no import) and bundle them so the runtime URLconf resolves.
def _pkg_py_modules(*dotted_pkgs):
    base = SPECPATH if "SPECPATH" in globals() else os.getcwd()
    mods = []
    for dotted in dotted_pkgs:
        for root, _dirs, files in os.walk(os.path.join(base, *dotted.split("."))):
            rel = os.path.relpath(root, base).split(os.sep)
            for fn in files:
                if fn.endswith(".py"):
                    mods.append(".".join(rel) if fn == "__init__.py" else ".".join(rel + [fn[:-3]]))
    return mods


hiddenimports += _pkg_py_modules("local.auth_app.urls", "local.api_app.urls")

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

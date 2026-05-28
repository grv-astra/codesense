#!/usr/bin/env python
"""Production entrypoint for the bundled Code Sense backend.

Applies DB migrations (creating the SQLite DB on first launch) then serves Django
via waitress. The Tauri shell launches this as the `codesense-server` sidecar:

    codesense-server <host> <port>     # e.g. codesense-server 127.0.0.1 8585

All configuration comes from environment variables set by the launcher
(CODESENSE_DATA_DIR, VLLM_BASE_URL, SCANNER_TOOLS_DIR, GRYPE_DB_CACHE_DIR,
COSIGN_KEY_DIR, ...). DEBUG defaults off (see settings.py).
"""
import os
import sys


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8585

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codesense.settings")

    import django
    django.setup()

    from django.core.management import call_command
    call_command("migrate", interactive=False, verbosity=0)

    from waitress import serve
    from codesense.wsgi import application

    print(f"Code Sense backend listening on http://{host}:{port}", flush=True)
    serve(application, host=host, port=port, threads=8)


if __name__ == "__main__":
    main()

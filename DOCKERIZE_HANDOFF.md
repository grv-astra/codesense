# Handoff: Dockerize Code Sense for client VM deployment

Repo: `https://github.com/grv-astra/codesense`, branch `main` (currently at `447a69a`).
**Target: the web app only** — Django backend (`server/`) + React frontend (`client/`).
Ignore `client/src-tauri/` entirely — that's a separate desktop `.exe` distribution track,
unrelated to this deployment.

## Read first
- [`HANDOVER_DEPLOY.md`](HANDOVER_DEPLOY.md) — the last session's deploy-readiness notes,
  including a **critical bug** about where scan data lives (see below, don't skip it).
- [`CLIENT_MACHINE_PREREQUISITES.md`](CLIENT_MACHINE_PREREQUISITES.md) — prereqs notes.
- `server/railway.json` / `client/railway.json` — an existing (unused-for-this-branch)
  reference for how each half is already meant to be started standalone.

## Architecture — two services, already separable

**Backend** (`server/`): Django + DRF, served via `waitress` (not gunicorn/uwsgi — already
wired, don't swap it). Python **3.13**. Entrypoint is already production-shaped:

```
python run_server.py 0.0.0.0 $PORT
```

`run_server.py` runs migrations, collects static, then serves. All config is env-var driven —
no code changes needed to containerize it. Key vars:

| Var | Purpose |
|---|---|
| `PORT` | listen port (also accepts host/port as argv, but env is what Docker will use) |
| `CODESENSE_DATA_DIR` | **must be a mounted volume** — see the git-working-tree bug below |
| `DJANGO_ALLOWED_HOSTS` | comma-separated, e.g. the client VM's domain/IP |
| `DJANGO_CORS_ALLOWED_ORIGINS` | comma-separated, wherever the frontend is served from |
| `DJANGO_SECRET_KEY` | set explicitly in prod (else auto-generated into `CODESENSE_DATA_DIR/secret_key` on first boot — fine too, as long as that dir persists) |
| `VLLM_BASE_URL` | optional — LLM verifier/enrichment **fail open** if unset (findings still work, just no TP/FP verification or AI enrichment). Can be deferred to a later pass. |
| `SEMGREP_RULES_DIR` | point at the bundled `dist/semgrep-rules` (copy it into the image) |

`server/requirements.txt` pins `semgrep>=1.90,<2` as a **pip package** — on Linux this gives
you a real `semgrep` CLI for free, no binary staging needed (that's only required for the
Windows desktop build, which uses OpenGrep instead — not relevant here).

**Gap to close:** the SBOM/vulnerability-scan feature also shells out to `grype` and `cosign`
binaries. Only Windows builds of those are currently staged in this repo (`dist/tools/windows`).
For Linux you'll need to fetch the Linux releases of both and put them on `PATH` (or wherever
`server/scanner/services/*` resolves tool paths from — grep for `tool_path(` and
`GRYPE_DB_CACHE_DIR`/`COSIGN_KEY_DIR` env vars). If the client doesn't need SBOM scanning on
day one, this can be deferred.

**Frontend** (`client/`): Vite/React, Node **>=20.19**. Build with `npm ci && npm run build`,
needs `VITE_BACKEND_URL` set **at build time** (browser-facing, points at wherever the backend
container is actually reachable from the client VM's users — not container-to-container
Docker networking). Serve the `dist/` output with `npm run start` (already scripted, wraps
`serve`) or swap in nginx.

## Critical bug — read before wiring the data volume

A real, already-hit bug: OpenGrep/Semgrep's directory walker returns **0 files** for any path
inside a git working tree. If `CODESENSE_DATA_DIR` (where uploaded/extracted scan sources live)
ends up nested inside wherever the Dockerfile does `git clone`/`COPY . .`, every zip-uploaded
scan will silently report 0 findings — no error anywhere. Mount `CODESENSE_DATA_DIR` as a
**named volume outside the image's source copy**, full stop. Full writeup in
[`HANDOVER_DEPLOY.md`](HANDOVER_DEPLOY.md) under "CRITICAL bug found + fixed."

## Database

SQLite, single file at `CODESENSE_DATA_DIR/app.sqlite3` (hardcoded in `codesense/settings.py`,
not currently swappable via env var). Fine for a single client VM at expected scale — flag it
if that assumption is wrong, since moving to Postgres is a real settings.py change, not just
config.

## ⚠️ Security issue to fix before this goes anywhere real

`run_server.py` was just changed to call the `create_admin_user` management command on every
startup. That command ([`server/local/auth_app/management/commands/create_admin_user.py`](server/local/auth_app/management/commands/create_admin_user.py))
creates a **hardcoded** account — `admin@codesense.dev` / `Admin@123` — if no user with that
email exists yet. Left as-is, **every fresh container/volume gets this exact publicly-known
login**. Fix before a real client deployment: either source the password from an env var (fail
if unset), or drop the auto-create and document a manual bootstrap step instead. Don't ship this
default as-is.

## Suggested container layout

1. `backend` — Python 3.13 base, `pip install -r server/requirements.txt`, copy `dist/semgrep-rules`
   in, install `grype`/`cosign` Linux binaries, `CMD ["python", "run_server.py"]` with `PORT` env.
2. `frontend` — Node build stage → static serve stage (`serve` or nginx).
3. `llm` (optional, defer if the VM is resource-constrained) — llama-server + GGUF; lives in the
   sibling `astra-model-host/` dir (not in this repo), currently CPU-only, ~30s/finding. Image
   size depends on model tier (1.5B ≈1GB vs 7B ≈4.68GB).
4. `nginx` (recommended) — single entry point, TLS, routes `/api/*` → backend, else → frontend.
5. `docker-compose.yml` tying it together with the named volume for `CODESENSE_DATA_DIR`.

## Verification before calling it done

- Backend: `cd server && .venv/Scripts/python.exe manage.py test` (or the container's Python)
- Frontend: `cd client && npm test` && `npx tsc --noEmit`
- A real zip-upload scan end-to-end against the containerized stack, confirming findings are
  non-zero (the git-working-tree bug above is exactly the failure mode that silently produces 0).

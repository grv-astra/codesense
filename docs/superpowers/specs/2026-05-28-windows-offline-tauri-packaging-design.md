# Code Sense — Offline Windows Desktop Packaging (Tauri)

- **Date:** 2026-05-28
- **Status:** Approved design (pre-implementation)
- **Author:** Brainstormed with Claude
- **Repo:** `yacm` (client = React/Vite, server = Django, model = `Astra_Code_reviewer_full`)

## 1. Problem statement

Code Sense is a full-stack security scanning platform: a React/Vite frontend, a Django + MongoDB backend, an AI code-review model (Qwen2.5-Coder-3B) served over an OpenAI-compatible API, plus SBOM/SCA tooling (Syft/Grype/Cosign) and an online central licensing server.

We need to ship it as a **single, installable Windows desktop application** that:

- runs fully **offline** with **no external services** (no separate MongoDB, no vLLM/Ollama server, no central license server),
- targets **CPU-only Windows** machines,
- feels like a **native desktop app** (not "open your browser to localhost"),
- can be **turned off when not in use** and restarted cleanly,
- enforces a **3-month license** that starts at first run, resists casual tampering, and degrades to read-only on expiry.

## 2. Goals / non-goals

### Goals
- One installer producing one launchable desktop app.
- Self-contained: SQLite (no MongoDB), bundled AI inference, bundled SBOM tooling, offline license.
- Preserve current functionality: both **SAST** (AI code review) and **SBOM/SCA** (dependency/CVE/license) scanning, projects, findings, users, RBAC, dashboard.
- Native-app UX via **Tauri** with a tray and a clean shutdown control.

### Non-goals
- Cryptographically unbreakable DRM. Threat model is "stops a normal user copying it or changing the date," **not** a skilled reverse-engineer (see §11).
- GPU acceleration (CPU-only target; GPU may work via llama.cpp if present but is not required or tuned for).
- Auto-update / online license renewal. Renewal = ship a new build/installer.
- Migrating an existing live MongoDB dataset. Installs start **fresh** (see §7).
- Multi-machine networked deployment. The app binds to loopback only.

## 3. Locked decisions (from brainstorming)

| Topic | Decision |
|-------|----------|
| Target hardware | CPU-only Windows |
| Data store | Migrate MongoDB → **SQLite** (clean, self-contained) |
| Tamper bar | "Stops a normal user copying it / changing the date" |
| License clock | **3 months from first run** (tamper-protected first-seen stamp + clock-rollback guard) |
| Scan scope | **Both** SAST (AI) **and** SBOM/SCA |
| DB bootstrap | **First-run setup screen** (create admin, seed permissions); no default credentials |
| Expiry behavior | **Read-only grace** (view existing data; block new scans/writes) |
| Packaging shell | **Tau​ri** (native-app feel; WebView2 + Rust shell + sidecars) |
| Shutdown | Tray control to turn the app off; "pause AI engine" to free RAM |

## 4. Architecture

```
┌──────────────────────── CodeSense.exe (Tauri) ───────────────────────┐
│  WebView2 window  ──HTTP──▶  Django backend (waitress, 127.0.0.1:8585)│
│  (React UI, prebuilt)         │  ├─ SQLite  (%LOCALAPPDATA%\CodeSense) │
│  system tray + menu           │  ├─ spawns ▶ llama-server.exe (GGUF)   │
│                               │  └─ shells ▶ syft / grype / cosign     │
└───────────────────────────────────────────────────────────────────────┘
```

- All listeners bind to **127.0.0.1 only** — nothing exposed on the network.
- The React app is built to static assets and served by the Tauri webview (custom protocol). It calls the Django backend over `http://127.0.0.1:8585`.
- Tauri's **sidecar** mechanism bundles and lifecycle-manages the Django backend executable and `llama-server.exe`.

### Component inventory
| Component | Today | After |
|-----------|-------|-------|
| Frontend | Vite dev/served separately | Built static assets inside Tauri bundle |
| Backend | Django dev server | Django frozen (PyInstaller) under **waitress**, run as Tauri sidecar |
| DB | MongoDB server | **SQLite** file in `%LOCALAPPDATA%\CodeSense` |
| AI inference | external vLLM | bundled **llama.cpp `llama-server.exe`** + quantized GGUF |
| Embeddings/RAG | Ollama + FAISS | **removed** (dead code — see §6) |
| SBOM tools | system Syft/Grype/Cosign | **bundled** binaries + offline Grype DB snapshot |
| Licensing | central server (HTTP) | **local offline** verifier |

## 5. Data layer: MongoDB → SQLite

**Approach:** Rewrite the ~10 model classes onto SQLite via the Django ORM, **preserving each class's public method signatures** so views/serializers/scanner code is largely untouched.

- All DB access already funnels through model classes (`UserModel`, `PermissionModel`, `ProjectModel`, `ScanModel`, `FindingModel`, `SbomModel`) plus one `MongoDBClient` ([common/db/__init__.py](../../../server/common/db/__init__.py)). `DATABASES` is currently `{}` (ORM unused), so there is no existing ORM schema to reconcile.
- **`LicenseModel`** ([licenses/models.py](../../../server/licenses/models.py)) is **not** migrated — offline licensing (§8) supersedes it with a signed stamp file + registry key, so the Mongo-backed license collection is dropped.
- **Field mapping:** flat/queryable fields → real columns with indexes; nested/document fields (`cvss[]`, `severity_counts`, `metrics`, `ecosystems`, `license{}`, `locations`) → `JSONField`.
- **Identifiers:** replace `ObjectId` `_id` with **string UUID** primary keys, still serialized to the API as `id` so the **frontend response shape is unchanged**.
- **Mongo surface to cover:** `find` (×20), `update_one`/`$set` (×16/×17), `count_documents` (×13), `find_one` (×12), `insert_many`/`insert_one`, `delete_one`/`delete_many`, with `skip`/`limit`/`sort` and operators `$in`, `$ne`, `$gte`, `$nin`, `$exists`. These map directly to ORM filters/slicing.
- **Aggregations (the hard part):** 9 `aggregate()` pipelines (dashboard analytics in `dashboard_views.py` and finding/sbom models) get **hand-ported** to ORM `values().annotate()` / `aggregate()` or raw SQL. Treated as a discrete, test-covered task.
- **Bootstrap:** configure `DATABASES` for SQLite at the app data path; on first launch, create the DB and run migrations. Replace `MongoDBClient` with a thin SQLite connection/bootstrap (or remove it once models no longer call it).

**Acceptance:** every existing model method returns the same shape it does today; dashboard numbers match a Mongo reference run on identical seed data.

## 6. Offline AI engine

- Convert `Astra_Code_reviewer_full` (Qwen2.5-Coder-3B) to **GGUF, Q4_K_M (~2 GB)** via llama.cpp conversion tooling.
- Bundle **`llama-server.exe`** (llama.cpp, OpenAI-compatible). Set `VLLM_BASE_URL=http://127.0.0.1:<port>/v1` and `VLLM_MODEL` to the served model id. **No application code change** — [server/scanner/rag/llm.py](../../../server/scanner/rag/llm.py) already speaks `/v1/chat/completions` over HTTP.
- **Remove dead code:** [server/scanner/rag/embeddings.py](../../../server/scanner/rag/embeddings.py), the Ollama/`langchain-community` dependency, and the `index.faiss` / `index.pkl` files. Verified: the live scan path ([scanner.py](../../../server/scanner/rag/scanner.py) → [analysis.py](../../../server/scanner/rag/analysis.py) → llm.py → extract.py) never imports embeddings or FAISS.
- Tune llama.cpp thread count to available cores; respect existing `SCAN_MAX_WORKERS`. Keep scans on background threads with progress polling so long CPU runs stay responsive.

**Performance note:** file-by-file 3B inference on CPU is slow (minutes for large repos). Acceptable per scope decision; UI must show clear progress and never appear hung.

## 7. Offline SBOM/SCA

- Bundle **Syft**, **Grype**, **Cosign** Windows binaries; invoke by bundled path (not PATH).
- Ship a **Grype vulnerability DB snapshot**; set `GRYPE_DB_AUTO_UPDATE=false` and a bundled `GRYPE_DB_CACHE_DIR`. CVE data is frozen at build time (acceptable for a 3-month license).
- Generate the Cosign signing keypair **locally on first run** using the existing `init_sbom_signing` management command; no network calls.

## 8. Offline licensing (replaces central server)

Remove the challenge/assertion HTTP flow in [server/licenses/services/auth.py](../../../server/licenses/services/auth.py) and the `require_assertion_jwt` central dependency. Replace with a **local offline verifier**:

- **First-run stamp:** on first launch, record a `first_seen` timestamp; `expiry = first_seen + 90 days`.
- **Signing:** the stamp record is **Ed25519-signed** with a private key the vendor holds; the **public key is embedded** in the build. Reuse [server/licenses/services/crypto.py](../../../server/licenses/services/crypto.py). Users cannot forge or edit the expiry without the private key.
- **Redundant storage:** write the signed stamp to **two locations** — an obfuscated file in `%LOCALAPPDATA%\CodeSense` **and** a Windows registry key. Deleting one does not reset the clock; the verifier takes the earliest valid `first_seen`.
- **Clock-rollback guard:** persist a monotonic **high-water-mark** timestamp (updated each run/heartbeat). If the system clock is earlier than the high-water-mark, treat as tampering.
- **Enforcement:** a single Django middleware/decorator computes license state (`active` | `expiring` | `expired/tampered`) once per request. On `expired`/`tampered`, **all write/scan endpoints return a license error**; read endpoints still work (**read-only grace**). A **warning banner** is surfaced to the UI during the final **7 days**.

## 9. First-run setup wizard

- On a fresh install (no admin user in SQLite) the UI shows a **setup screen**: create admin (email + password), which seeds the admin user and default role permissions (reusing existing password hashing/validation).
- No default credentials ship.
- First-run is also where the license `first_seen` stamp is written.

## 10. Frontend changes

- **Backend URL:** change [client/src/lib/api.ts](../../../client/src/lib/api.ts) from `http://${window.location.hostname}:8585` to a fixed `http://127.0.0.1:8585` (the `window.location.hostname` assumption breaks under Tauri's `tauri.localhost` origin).
- **Setup wizard:** new first-run route/flow (§9).
- **License UX:** expiry warning banner (final 7 days) and a read-only mode that disables/explains blocked write actions after expiry.
- Build output is embedded in the Tauri bundle.

## 11. Production hardening (required for distribution)

Current settings are dev-grade and must be fixed before shipping:
- `DEBUG=False`.
- Replace the hardcoded insecure `SECRET_KEY` with one **generated and persisted at first run** (per-install).
- `ALLOWED_HOSTS=['127.0.0.1','localhost']`.
- Stop shipping real secrets in `.env` (`server/.env` currently tracked; `COSIGN_PASSWORD` etc. should be generated locally, not bundled).
- Tighten CORS to the local origin.

## 12. Threat model & limitations (explicit)

Anything running on a user-controlled machine **can** ultimately be bypassed (binary patching, model extraction, OS-level clock manipulation). This design targets **casual misuse**: it stops a normal user from copying the install to dodge expiry, editing the stored date, or rolling back the system clock. It does **not** claim resistance to a determined reverse-engineer. If stronger resistance is later required, compiling the license module to a native extension and/or Authenticode integrity checks are focused follow-ups.

## 13. Data & filesystem layout

- **Install dir:** `C:\Program Files\CodeSense\` — app, backend exe, `llama-server.exe`, model GGUF, Syft/Grype/Cosign, Grype DB snapshot, embedded public license key.
- **Per-user data:** `%LOCALAPPDATA%\CodeSense\` — `app.sqlite3`, Cosign keys, license stamp file, logs, scan temp dirs.
- **Registry:** one key under `HKCU\Software\CodeSense\` for the redundant license stamp.
- **Ports:** backend `127.0.0.1:8585`; `llama-server` on a private loopback port.

## 14. Testing strategy

- **Unit:** SQLite model methods (parity with documented shapes); license verifier (active/expiring/expired/rollback/missing-stamp/forged-stamp); read-only-grace gate.
- **Integration:** dashboard aggregation parity vs. a Mongo reference on identical seed data; full code scan and SBOM scan against fixture inputs.
- **E2E on a clean CPU-only Windows VM:** install → first-run setup → create project → code scan (AI) → SBOM scan → view findings/dashboard → tray *Pause AI engine* / *Quit* / relaunch → simulate expiry and clock-rollback → confirm read-only grace and banners.

## 15. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Aggregation port introduces dashboard regressions | Dedicated task with parity tests vs. Mongo reference |
| CPU AI scans feel "hung" | Background threads + visible progress; *Pause AI engine* control |
| PyInstaller-frozen Django misses dynamic imports | Explicit hidden-imports list; smoke-test the frozen exe early |
| Tauri sidecar orphan processes on crash/quit | Use Tauri sidecar lifecycle + explicit shutdown handler; test kill paths |
| WebView2 absent on target machine | Bundle the **fixed-version WebView2 runtime** for a guaranteed-offline install |
| Grype DB staleness | Documented limitation; refresh at each repackage |
| Stale committed secrets leak | Remove from VCS, generate locally at first run |

## 16. Phased plan of action

0. **Prep:** pin component versions (llama.cpp, Syft/Grype/Cosign, Tauri, WebView2 runtime); stand up a clean CPU-only Windows test VM.
1. **SQLite migration:** model rewrite (signatures preserved) + JSON fields + UUID ids + 9 aggregation ports + DB bootstrap/seed. *(Heaviest backend task.)*
2. **Offline AI:** GGUF conversion, bundle `llama-server`, repoint env, delete Ollama/FAISS.
3. **Offline SBOM:** bundle Syft/Grype/Cosign + Grype DB snapshot; local Cosign init.
4. **Offline licensing:** first-seen stamp, redundant tamper store, rollback guard, read-only-grace middleware; rip out central calls.
5. **Frontend:** fixed backend URL, setup wizard, expiry/read-only UX.
6. **Tauri shell:** sidecar config for backend + llama-server, tray (Open / Pause AI engine / Quit), graceful shutdown, bundle fixed-version WebView2.
7. **Packaging:** PyInstaller backend build, Tauri bundler → MSI/NSIS installer, data-dir setup, Authenticode signing, production settings.
8. **E2E test:** full clean-VM run-through per §14.

**Size estimate:** ~2.5–3 GB installed (dominated by the GGUF model + Grype DB). **Heaviest phases:** 1 (SQLite) and 6 (Tauri integration); the rest is mostly mechanical bundling.

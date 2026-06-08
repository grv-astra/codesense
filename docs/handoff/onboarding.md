# Code Sense (`yacm`) — Developer Onboarding Guide

*Prepared from the 2026-05-31 handoff package and a full read of the bundled repository (`codesense-repo.bundle`, branch `lsast-handoff-2026-05-31`, 76 commits). Assumes no prior knowledge of the project.*

---

## 1. Executive summary

**Code Sense** (internal repo name `yacm`) is an **offline, self-contained desktop application for application security scanning**. It packages a static analysis engine, a software-composition / SBOM toolchain, and a local large language model into a single installable app that runs entirely on the analyst's laptop — **no network access at runtime, no telemetry, no cloud calls**. This "airgapped" property is the product's central selling point and the constraint that shapes nearly every technical decision; the intended customer is a security-conscious organization (the docs reference a *bank deployment dossier*) that cannot send source code to a third-party service.

The app does three things:
1. **SAST (static code analysis)** via a pipeline called **LSAST** — Semgrep/OpenGrep finds candidate vulnerabilities, a local LLM judges each one as a true/false positive, and a fusion step decides what to show.
2. **SCA / SBOM** — generates a software bill of materials and scans dependencies for known CVEs and risky licenses using bundled Syft / Grype / Grant / Cosign binaries against a frozen offline CVE database.
3. **Reporting & management** — a web UI (running inside the desktop shell) for projects, scans, findings, dashboards, users, and role-based access.

Architecturally it is a **Tauri (Rust) desktop shell** that supervises **two local sidecar processes**: a **Django REST backend** (frozen with PyInstaller) and a **llama.cpp server** hosting a quantized model. The frontend is a **React + Vite single-page app** rendered in the OS webview.

The codebase is **functional and actively developed but pre-1.0 and rough in places**. It carries roughly 70+ unpushed commits, an uncommitted work session, a couple of half-migrated subsystems (two parallel licensing schemes, a stale MongoDB-era `.env`), and — most urgently — a **likely software-license compliance problem with the bundled AI model**. The scanner test suite is healthy (91 tests).

> **The single most important thing to know on day one:** the AI model that ships in the product (`astra.gguf`, a Qwen2.5-Coder-**3B** model) appears to be under a **non-commercial license**, and it is also the *wrong kind* of model for the job (a code-completion model, not an instruction-following one), which is why the "smart" parts of the scanner underperform. Both problems are solved by the same planned work: swapping in an instruction-tuned, Apache-licensed model. This is documented as the top priority.

---

## 2. Project purpose

The product exists to let organizations **scan their own source code and dependencies for security problems without that code ever leaving the machine.** Conventional SAST/SCA tools either run in the cloud or phone home for rules, CVE data, or telemetry. Code Sense deliberately rejects all of that:

- All scanning engines, rules, the CVE database, and the AI model are **bundled into the installer**.
- All network listeners bind to `127.0.0.1` only.
- There is **no central server dependency at runtime** (there *is* a vestigial "central license server" provisioning path in the code, but the shipping product uses a self-contained offline license instead — see §7).

The "intelligence" angle that differentiates it from running raw Semgrep is the **LLM verification layer**: a local model reviews each Semgrep finding in context to cut down on false positives and to author human-readable descriptions and remediation advice — again, all locally.

The intended user is a security analyst or operator who: creates a *project*, kicks off a *scan* (by uploading a zip, pointing at a GitHub repo, or uploading an SBOM), waits for the background pipeline to finish, then triages the resulting *findings* in the UI.

---

## 3. Architecture overview

There is an existing, accurate architecture document at **`docs/Code_Sense_Architecture.md`** — read it. Here is the practical mental model.

### Runtime topology (everything on one laptop, loopback only)

```
┌──────────────── User's laptop — loopback only, no egress ────────────────┐
│                                                                          │
│   ┌──── Code Sense (Tauri shell, Rust) ────┐                             │
│   │  System tray: Open / Pause AI / Quit   │                             │
│   │  WebView window → React + Vite UI      │                             │
│   └───────────────┬────────────────────────┘                            │
│         spawns &   │  HTTP → http://127.0.0.1:8585                       │
│         supervises │                                                     │
│         (sidecars) ▼                                                     │
│   ┌──── Django backend (waitress) @ 127.0.0.1:8585 ────┐                 │
│   │  REST API · JWT auth · RBAC · license middleware    │                │
│   │     │                                               │                │
│   │     ├── HTTP /v1/chat ──► llama-server (llama.cpp)  │                │
│   │     │                     @ 127.0.0.1:8001          │                │
│   │     │                     serves astra.gguf (CPU)   │                │
│   │     ├── subprocess ─────► Syft / Grype / Grant /    │                │
│   │     │                     Cosign / OpenGrep         │                │
│   │     ├── reads ──────────► frozen Grype CVE DB        │                │
│   │     └── read/write ─────► SQLite + license stamp +  │                │
│   │                           cosign keys                │                │
│   └─────────────────────────────────────────────────────┘               │
│                                                                          │
│   ✗ no inbound ports beyond loopback   ✗ no outbound traffic             │
└──────────────────────────────────────────────────────────────────────────┘
```

### The three processes

1. **Tauri shell (`client/src-tauri/src/main.rs`, ~197 lines of Rust).** The native window + system tray. Its real job is **lifecycle management**: on launch it spawns the two sidecars (`codesense-server` on port 8585 and `llama-server` on port 8001) and on quit it kills them cleanly so no orphan processes or held ports remain. The tray has a "Pause AI" toggle that stops/restarts the llama sidecar to free its RAM.

2. **Django backend (`server/`), frozen by PyInstaller into a binary called `codesense-server`, served by `waitress`.** This is where essentially all the application logic lives: the REST API, authentication, authorization, license gating, scan orchestration, and all the scanner pipeline code. **Critical gotcha: the running app uses the *frozen* binary, not your Python source.** Changing a `.py` file does nothing until you re-freeze (see §10/§14).

3. **llama-server (llama.cpp), serving `astra.gguf`.** A local OpenAI-compatible inference server on `127.0.0.1:8001`. The backend talks to it through `VLLMClient` in `server/scanner/rag/llm.py`.

### The two scanning pipelines

- **LSAST (SAST / code scanning)** — the marquee feature:
  `Semgrep/OpenGrep detector → finding normalizer → LLM verifier (TP/FP) → fusion (show/suppress/needs_review) → [LLM report enrichment] → persist to SQLite`. Code in `server/scanner/rag/`. Entry point: `scanner.rag.scanner.scan_folder()`.
- **SBOM / SCA (dependency scanning)** — `server/scanner/services/sbom_pipeline.py`. Uses external binaries (Syft to generate the SBOM, Grype for CVEs against the frozen DB, Grant for license policy, Cosign to sign the SBOM).

### Tech stack at a glance

| Layer | Technology |
|---|---|
| Desktop shell | Tauri v2 (Rust), system webview |
| Frontend | React 19, Vite 7, TypeScript, TanStack Router + Query + Form, Tailwind v4, Radix UI, Recharts, axios |
| Backend | Django 5.2 + Django REST Framework, served by waitress |
| Database | SQLite (per-user, in app data dir) |
| AI inference | llama.cpp (`llama-server`), Qwen2.5-Coder-3B GGUF |
| SAST engine | OpenGrep (an OSS Semgrep fork) + bundled rules |
| SCA tools | Syft, Grype (+ frozen CVE DB), Grant, Cosign |
| Packaging | PyInstaller (backend) + Tauri bundler (app), per-OS build scripts |

---

## 4. Folder structure explanation

Repo root contains three build docs (`BUILD.md`, `BUILD_MACOS.md`, `WINDOWS_BUILD_START_HERE.md`) and three top-level code directories.

```
yacm/
├── client/                      # Tauri desktop app + React frontend
│   ├── src/                     # React SPA (the UI)
│   │   ├── routes/              # TanStack file-based routes (the page tree)
│   │   ├── components/          # UI components (atomic / molecule / charts / permissions / update)
│   │   ├── hooks/               # React-Query data hooks (use-auth, use-scans, use-finding, …)
│   │   ├── services/            # Typed API clients, one per domain (auth, scan, finding, …)
│   │   ├── types/               # TypeScript domain types
│   │   ├── lib/                 # api.ts (axios client), auth.ts (auth singleton)
│   │   ├── config/              # route-permissions.ts (which permission gates which route)
│   │   └── utils/               # permissions helpers, formatters
│   └── src-tauri/               # Rust shell: main.rs, tauri.conf.json, icons, entitlements
│
├── server/                      # Django backend (the brain)
│   ├── codesense/               # Django project: settings.py, urls.py, wsgi/asgi
│   ├── common/                  # shared ORM base (UUIDModel)
│   ├── local/
│   │   ├── api_app/             # projects, scans, findings, SBOM — models, views, serializers, urls
│   │   └── auth_app/            # users, roles, permissions, JWT, setup, account integrity
│   ├── licenses/                # offline license + (vestigial) central-server provisioning
│   ├── scanner/                 # the scanning engines
│   │   ├── rag/                 # ★ LSAST pipeline (detector, normalizer, verifier, fusion, enricher, llm)
│   │   ├── services/            # sbom_pipeline, scan_service, tools
│   │   └── tests/               # 91 scanner unit tests
│   ├── codesense.spec           # PyInstaller freeze config
│   ├── requirements.txt
│   └── manage.py / run_server.py
│
├── scripts/                     # build & ops tooling
│   ├── build_windows.ps1, build_macos.sh, …
│   ├── offline_sbom/            # fetch/stage the SBOM tools + semgrep rules for bundling
│   └── eval/                    # SAST accuracy eval harness (dev-host only, never bundled)
│
└── docs/                        # architecture, deployment dossier, design specs & plans
    └── superpowers/             # dated specs/ and plans/ (the project's design-doc trail)
```

A note on naming: **`server/scanner/rag/`** is the most important directory in the codebase. The name "rag" (retrieval-augmented generation) is historical — there is no real RAG/embedding system anymore; it now houses the LSAST pipeline. Don't read meaning into the folder name.

The `docs/superpowers/` folder is a chronological trail of design specs and implementation plans (dated filenames). It's the best source for *why* things are the way they are, and worth skimming in date order.

---

## 5. Key business rules

These are the rules that govern behavior and that you can break without the type-checker noticing. Most live in the scanner pipeline.

**Finding fields are split between deterministic and AI-authored, and the boundary is sacred.**
- `title` = the **Semgrep rule name** (the last dotted segment of the rule's `check_id`, e.g. `sequelize-raw-query`), *not* the prose message. (`finding_normalizer._rule_name()`.)
- `description` / `security_risk` = the Semgrep message (or an LLM-authored version if enrichment succeeded).
- `mitigation` = LLM-authored remediation, or empty.
- **`cwe`, `severity`, `file_path`, and line numbers are ALWAYS deterministic and must NEVER be authored by the LLM.** The model is weak enough to hallucinate these, and a wrong CWE/severity/location in a security tool is dangerous. The enrichment pass is explicitly forbidden from touching them.

**The verifier never silently drops a finding (fail-open / fail-safe).**
- The LLM verdict (`server/scanner/rag/llm_verifier.py`) classifies each finding TP or FP. On *any* failure (model error, unparseable output), it returns a **low-confidence `TP`** so the finding is preserved for human review — never suppressed.
- **Fusion rules** (`server/scanner/rag/fusion.py`) decide display from verdict + severity:
  - verdict `TP`, any severity → **show**.
  - verdict `FP`, severity low/medium → **suppress** (status `filtered`).
  - verdict `FP`, severity high/critical → **needs_review** (a high-severity finding is *never* suppressed on the model's say-so; it's flagged instead).
- Severity ("how bad if real") and confidence ("how sure is the verifier") are kept as **separate axes** and deliberately not blended.

**Report enrichment is fail-open and toggleable.**
- A *second, separate* LLM pass (`report_enricher.py`) authors the human-facing fields. If it fails or is disabled, the deterministic Semgrep-derived fields remain. Controlled by env `LSAST_ENRICH_FINDINGS` (default on; set to `0` to disable, which also nearly halves scan time).

**CWE derivation is layered, and never fabricated for security rules.**
- `derive_cwe()` tries: explicit `metadata.cwe` → rule-name keyword map → OWASP-tag map → non-security category → `CWE-710` for lint/style rules. Returns empty (→ "CWE-Unknown") only when nothing fits. It deliberately uses long, unambiguous keywords (a regression test guards against e.g. matching "rce" inside "source").

**Scan concurrency is limited.**
- ZIP/SBOM scans run on a single global background thread (a second concurrent request gets HTTP 409). GitHub scans use a small pool capped at `MAX_CONCURRENT_SCANS = 5` (HTTP 429 beyond that). Scans are **background threads inside the Django process**, not a real task queue.

**License grace = read-only, not lockout.**
- When the offline license is expired or tampered, the app enters **read-only mode**: GET/HEAD/OPTIONS still work (you can view existing data and renew), but writes/scans are blocked with HTTP 403. Login, setup, and license endpoints stay reachable. (`licenses/middleware.py`.)

**First-run setup creates the admin and starts the license clock.**
- The app is "unconfigured" until one Admin exists. Creating the initial admin (`auth_app/services/setup.py`) seeds default (all-false) permissions for `user` and `manager` roles and stamps the license `first_seen`.

**Admin is all-powerful; other roles are explicitly granted.**
- The `admin` role bypasses permission checks entirely. All other roles get only the permission keys explicitly set for them (default false).

---

## 6. Data model relationships

All persistent data is in **SQLite**. The ORM models are plain Django models, but there's an important quirk:

> **There are no real foreign keys.** Relationships are modeled as **indexed `CharField` ID columns** (`project_id`, `scan_id`) holding UUID strings, *not* Django `ForeignKey` fields. So there's no DB-level referential integrity, no cascade, and no `select_related`. Joins are done manually in the model-helper classes. This is a deliberate (if debatable) pattern inherited from an earlier MongoDB design — keep it in mind before you assume `scan.findings` gives you related objects (it doesn't; `findings` is an integer *count*).

### Entities and how they relate

```
User (auth_app.users)
  └─ role (string) ──► RolePermission (auth_app.permissions)   # role → {permission_key: bool}

Project (api_app.projects)
  │  created_by → User.id (string)
  ├──< Scan (api_app.scans)            # SAST scans;  project_id → Project.id
  │       └──< Finding (api_app.findings)   # scan_id → Scan.id
  └──< SbomScan (api_app.sbom_scans)   # dependency scans; project_id → Project.id
          ├──< SbomFinding (api_app.sbom_findings)            # CVE findings; scan_id → SbomScan.id
          └──< SbomLicenseFinding (api_app.sbom_licenses_findings)  # license findings; scan_id → SbomScan.id
```

- **User → RolePermission**: linked by the role *string* (e.g. `"manager"`), not an FK. `admin` is special-cased in code and has no row (always all-true).
- **Project → Scan / SbomScan**: one project has many of each. `project_id` string column, indexed.
- **Scan → Finding**: one SAST scan has many findings. Deleting a scan also deletes its findings (done explicitly in `ScanModel.delete_scan`, not by cascade).
- **SbomScan → SbomFinding + SbomLicenseFinding**: two separate child tables — CVE vulnerabilities and license findings respectively.
- All tables use a **UUID primary key** (`common/orm.py: UUIDModel`) and most have `deleted` boolean flags for **soft deletes** (though scans/findings are hard-deleted on delete).

### Finding model — the one to know well

`Finding` fields: `scan_id, created_by, cwe, cvss_vector, cvss_score, code, title, description, severity, file_path, code_snip, security_risk, mitigation, status, deleted, approved, reference, created_at`.

> **Important persistence trap:** `FindingModel.insert_many` only writes keys that are actual model fields and **silently drops everything else.** The pipeline computes useful runtime fields like `confidence`, `verifier_reason`, `lines`, and `affected` — but **these are not Finding columns, so they never reach the database.** If you want the UI to show verifier confidence/reason, you need a migration to add those columns first. (Noted in next-steps as a small future task.)

`status` values seen in the pipeline: `open` (default), `filtered` (suppressed FP), `needs_review` (FP but high-severity). `approved` is a human triage toggle (`validate_finding` permission).

---

## 7. Authentication and authorization flow

### Authentication (who you are)

- **Custom JWT, not Django sessions or DRF auth classes.** Login (`POST /api/auth/login`) verifies the password (bcrypt) and issues an **HS256 JWT** (`auth_app/utils/jwt.py`) carrying `id`, `role`, `email`, `name`, with a **60-minute expiry**.
- The frontend stores the token in **`localStorage`** (`auth_token`) and attaches it as a `Bearer` header via an axios interceptor (`client/src/lib/api.ts`). A 401 anywhere triggers automatic logout + redirect to `/login`.
- **There is no refresh-token mechanism** — when the 60-min token expires you're bounced to login.
- The DRF/middleware-based auth is **commented out** (`auth_app/middlewares.py` is entirely commented; `settings.py` registers no DEFAULT_AUTHENTICATION/PERMISSION classes). Auth is enforced **per-view via decorators**, not globally. A view with no decorator is effectively unauthenticated.

### Authorization (what you can do)

Enforced by **decorators** in `auth_app/permissions/decorators.py`, applied per view method:
- `@require_authentication()` — valid token required.
- `@require_role("Admin")` — role must be in an allow-list.
- `@require_permission("create_scan")` — the role must have that permission key set true. **This is the main one used throughout the API.**

All three decorators also run an **account-integrity check** (`verify_payload_user`): they re-load the user from the DB and compare a snapshot (email, role, password fingerprint, etc.) against a signed registry file (`protected_accounts.json`). If a protected account was tampered with locally, the request is rejected. This is an anti-tamper feature for the offline deployment, not normal web auth.

The permission keys are a fixed list (`PermissionModel.get_all_permission_keys()`): `create/delete/update/view_project`, `view/create/update/delete_scan`, `view/validate/delete_finding`, `create/update/delete/view_report`. The `admin` role bypasses all checks; other roles get explicitly-granted keys (default all false). Permissions are editable at runtime by an admin (`SetPermissionsView`).

**Frontend authorization is advisory only.** `ProtectedRoute` / `route-permissions.ts` hide routes the user lacks permission for, but the backend decorators are the real enforcement. Never trust the frontend gate.

### Two licensing systems (this is confusing — read carefully)

The `licenses/` app contains **two different schemes**, and the shipping product uses only one:
1. **Offline license (current, in use):** `licenses/services/offline_license.py` + `middleware.py`. A self-contained, HMAC-signed, time-limited license (default 90 days from first run) stored redundantly in a file *and* an OS store (Windows registry / macOS plist) to resist deletion and clock-rollback. Drives the read-only grace mode.
2. **Central-server provisioning (vestigial):** `licenses/services/auth.py` (`require_assertion_jwt`), `provision_local.py`, references to a `CENTRAL_URL`. This is an older online-activation design. **The `@require_assertion_jwt(...)` decorators are commented out on the scan views.** Treat this as legacy/inactive unless told otherwise — but don't delete it without confirming, since the deployment dossier may still reference it.

---

## 8. API architecture

A conventional **Django REST Framework** API, all under `/api/`, all on loopback `127.0.0.1:8585`. Views are mostly DRF `APIView` classes with per-method permission decorators. Routing is in `server/codesense/urls.py` → per-app `urls/` modules.

### Route map (the surface you'll actually call)

| Area | Method & path | Purpose | Guard |
|---|---|---|---|
| **Auth** | `POST /api/auth/login` | Log in, get JWT | none |
| | `GET /api/auth/setup` / `POST .../setup` | First-run admin bootstrap | none / 409 if done |
| | `GET /api/auth/permissions/me` | My role's permissions | authenticated |
| | `POST /api/auth/permissions/set` | Edit a role's permissions | Admin |
| | user CRUD under `/api/auth/users/` | manage users | permission-gated |
| **License** | `GET /api/license/` | License state | none |
| **Projects** | `/api/projects/` CRUD | manage projects | `*_project` perms |
| **Scans (SAST)** | `POST /api/scans/create/` | Upload ZIP, start scan | `create_scan` |
| | `POST /api/scans/github/` | Clone+scan a GitHub repo | `create_scan` |
| | `GET /api/scans/<id>/` · `DELETE /api/scans/delete/<id>/` | scan detail / delete | `view`/`delete_scan` |
| | `GET /api/scans/project/<project_id>/?type=sca\|sbom` | list scans | `view_scans` |
| **Scans (SBOM)** | `POST /api/scans/sbom/create/` | Upload project zip → SBOM scan | `create_scan` |
| | `POST /api/scans/grype/create/` | Upload an existing SBOM file | `create_scan` |
| | `GET/DELETE /api/scans/sbom/<id>/` | SBOM scan detail / delete | gated |
| **Findings** | `GET /api/findings/scan/<scan_id>/` | findings for a scan (paginated) | `view_findings` |
| | `GET /api/findings/scan/csv/<scan_id>/` | CSV export | `create_report` |
| | `GET /api/findings/scan/sbom/<id>/` · `.../sbom/licenses/<id>/` | SBOM findings / license findings | gated |
| | `PATCH /api/findings/approve/<id>/` | toggle approved | `validate_finding` |
| | `DELETE /api/findings/delete/<id>/` | soft-delete finding | `delete_finding` |
| | `GET /api/findings/<id>/` | finding detail | `view_findings` |
| **Dashboard** | `GET /api/dashboard/` | aggregate counts/charts | authenticated |

### Patterns and conventions

- **Scans are asynchronous.** `POST .../create/` validates, persists a `queued` scan row, spins up a **background thread** to run the pipeline, and returns **HTTP 202** immediately. The client **polls** the scan-detail endpoint for `status` (`queued → in_progress → completed/failed`) and progress counters. There's no websocket/SSE.
- **Pagination** is manual `?page=&limit=` with a `{items, pagination:{total,page,limit,pages}}` envelope, implemented repeatedly in each model class.
- **Serialization is hand-rolled** in `*_models.py` "model helper" classes (static `serialize()` methods), *not* DRF serializers for output. DRF serializers exist mainly for *input* validation (e.g. `ScanStartSerializer`).
- **CSRF is exempted** on the upload views (`@csrf_exempt`); auth is the JWT bearer header.
- **CORS** is locked to the Tauri webview origins (`tauri://localhost`, `http(s)://tauri.localhost`) plus the Vite dev server; allow-all only in DEBUG.
- The architecture is **layered**: `urls → views (HTTP + authz) → model-helper classes (business/query logic) → Django ORM models`. Views stay thin-ish; query logic lives in the `*Model` helper classes.

---

## 9. Frontend architecture

A **React 19 + Vite + TypeScript** SPA living in `client/src/`, rendered inside the Tauri webview. It talks only to `http://127.0.0.1:8585`.

### Key libraries and what they're for
- **TanStack Router** — file-based routing under `src/routes/`. Layout routes prefixed `_auth` (guest/login) and `_authenticated` (the app). The `$param` segments are dynamic (e.g. `scan/$scanId/findings.tsx`).
- **TanStack Query** — all server state (caching, polling, mutations). Data access is wrapped in hooks under `src/hooks/` (`use-auth`, `use-scans`, `use-finding`, `use-project`, `use-license`, `use-user`, `use-setup`).
- **TanStack Form** — forms.
- **Tailwind v4 + Radix UI** — styling and headless primitives. Components are organized atomic / molecule / charts.
- **Recharts** — dashboard charts (`src/components/charts/`).
- **axios** — the HTTP client, centralized in `src/lib/api.ts` (`BaseApiClient`) with token-injection and 401-handling interceptors.

### Layering
```
routes/ (pages)  →  hooks/ (React-Query data hooks)  →  services/ (typed API clients)  →  lib/api.ts (axios)
                          ↑                                  ↑
                    components/ (UI)                    types/ (domain types)
```
Each domain has a matching trio: `types/scan.ts` + `services/scan.service.ts` + `hooks/use-scans.tsx`. Follow that pattern when adding features.

### Auth & permission handling on the client
- Token in `localStorage`; `lib/auth.ts` is a small singleton tracking auth state; `lib/api.ts` injects the bearer header and force-logs-out on 401.
- `use-auth` loads the current user (`getMe`) and the role's permission map.
- **Route guarding**: `_authenticated` layout requires a token; `ProtectedRoute` + `config/route-permissions.ts` + `utils/permissions.ts` hide pages the role can't access. Remember: **this is UX only; the backend decorators are the real gate.**

### Notable UI areas
- `routes/setup.tsx` — first-run admin creation.
- `routes/_authenticated/scan/start/*` — the scan-kickoff flows (upload zip, GitHub repo, upload SBOM, etc.).
- `routes/_authenticated/scan/$scanId/*` and `finding/$findingId.tsx` — scan progress + finding triage (the core analyst workflow).
- `components/update/*` — live scan-progress / findings update views (polling).
- `components/molecule/license-banner.tsx` — surfaces the expiring/expired/read-only license state.

---

## 10. Important files to read first

Read in roughly this order to get productive fastest:

**Orientation (the handoff package, ~20 min):**
1. `README.md` (handoff) and `00-SESSION-NARRATIVE.md` — what the last session did and why. This is "the chat log."
2. `02-NEXT-STEPS.md` — the prioritized to-do list (the model license + model swap dominate).
3. `CLAUDE.md` — concise gotchas, especially the freeze-and-swap loop and the model limitations.

**Architecture & design:**
4. `docs/Code_Sense_Architecture.md` — the real architecture diagram + data flow.
5. `docs/superpowers/specs/2026-05-29-sast-accuracy-lsast-redesign-design.md` — why LSAST is shaped the way it is.
6. `docs/superpowers/specs/2026-05-31-instruction-tuned-verifier-model-swap-scope.md` — the model-swap plan **and the §9 license blocker.** Read §9 carefully.

**The backend core (where you'll spend your time):**
7. `server/codesense/settings.py` and `server/codesense/urls.py` — config + route map.
8. `server/scanner/rag/scanner.py` → `lsast_scanner.py` — the scan pipeline top-to-bottom. **Start here for anything scan-related.**
9. `server/scanner/rag/llm_verifier.py`, `fusion.py`, `report_enricher.py`, `semgrep_detector.py`, `finding_normalizer.py` — the pipeline stages and the business rules in §5.
10. `server/scanner/rag/llm.py` — the LLM client (and the FIM-model quirks you'll need to undo during the swap).
11. `server/local/api_app/models/orm.py` + the `*_models.py` helpers — the data model and query layer.
12. `server/local/auth_app/permissions/decorators.py` — how authz actually works.
13. `server/licenses/services/offline_license.py` + `middleware.py` — licensing/grace.
14. `client/src-tauri/src/main.rs` — how the desktop shell launches and supervises everything.

**Frontend:**
15. `client/src/lib/api.ts`, `client/src/hooks/use-auth.tsx`, and one full vertical slice (e.g. `types/scan.ts` + `services/scan.service.ts` + `hooks/use-scans.tsx` + a `routes/_authenticated/scan/...` page).

**Tests (the spec-by-example):**
16. `server/scanner/tests/` — 91 tests; the fastest way to understand expected behavior of the pipeline.

---

## 11. Current technical debt

- **The frozen-backend dev loop is painful.** Because the app runs a PyInstaller binary, verifying any backend change end-to-end requires re-freezing and swapping the binary into the installed app (the narrative documents doing this 3×). There's no hot-reload for the packaged app. Day-to-day you can run `manage.py runserver`/`run_server.py` against the source, but "is it really fixed in the product" needs the freeze loop.
- **Stale, MongoDB-era `.env.example`.** It still lists `MONGODB_URI` / `MONGO_DB_NAME` even though the project migrated to SQLite (see `docs/superpowers/plans/2026-05-28-phase1-sqlite-migration.md`). Misleading for newcomers.
- **Hand-rolled serialization & pagination duplicated across every model helper.** Lots of near-identical `serialize()`/`find_by_*`/pagination code. A DRF serializer/viewset refactor would remove hundreds of lines.
- **No foreign keys / referential integrity.** Relationships are loose string IDs; deletes are manual multi-step operations. Easy to orphan rows.
- **Pipeline-computed fields are silently dropped on persist** (`confidence`, `verifier_reason`, `lines`, `affected`) because they aren't Finding columns — so the UI can't show verifier metadata without a migration.
- **Scans run as raw background threads inside the web process**, gated by module-level globals/locks and a single-scan-at-a-time constraint for zip/SBOM. No real task queue, no durable retry, lost on process restart, and progress is poll-only.
- **Two parallel licensing systems**, one of them (central-server provisioning) effectively dead but still in the tree with commented-out decorators. Confusing; needs a decision to fully remove or revive.
- **Performance: 2 sequential LLM calls per visible finding** (verifier + enricher), single-threaded → ~9 min for a ~50-finding scan. Batching/merging the two calls is the obvious win (noted in next-steps #3).
- **~70+ unpushed commits + an uncommitted 14-file session.** The repo state is fragile until someone with GitHub credentials pushes (`git push` is blocked in the non-interactive environment the work was done in — needs a human terminal).
- **Inconsistent view base classes** (mix of DRF `APIView` and raw `JsonResponse`), and some hardcoded fallback IDs in views (e.g. a literal `triggered_by` default user id).

---

## 12. Known risks

- **⚠️ MODEL LICENSE — likely compliance violation (highest priority).** The shipped model `astra.gguf` is a fine-tune of **Qwen2.5-Coder-3B**, which (per Hugging Face verification in the scope doc) is under a **non-commercial `qwen-research` license**. Notably, its 0.5B/1.5B/7B/14B/32B siblings are Apache-2.0 — *only the 3B is restricted.* Shipping it in a commercial product is almost certainly outside the license. **Action: confirm the exact base-model lineage with whoever fine-tuned it, get legal sign-off, and plan to move off the 3B regardless of the quality work.**
- **The AI verifier currently provides little value (and could mislead).** Because the bundled model is a **fill-in-the-middle completion model, not instruction-tuned**, the verifier **never emits `FP`** — it rubber-stamps everything `TP` (even a safe parameterized query). So *nothing is ever suppressed*. This is currently fail-safe (you see all findings), but it means the headline "AI reduces false positives" feature isn't actually working yet. The report-enricher similarly only succeeds ~34% of the time. Both are fixed by the instruction-tuned model swap.
- **Secrets in the repo / weak defaults.** The JWT signing secret has a **hardcoded fallback** in `auth_app/utils/jwt.py` (`"nodeBetter+ImLe@theragicToThis"`) used if `JWT_TOKEN_SECRET` is unset. `.env.example` contains a literal `COSIGN_PASSWORD="admin@123"`. The offline-license secret falls back to a constant in dev. For a security product shipped to banks, these need build-time injection and rotation, and the committed examples should be scrubbed.
- **Offline license tamper model is intentionally modest.** It's designed to stop a normal user copying the install or changing the clock — *not* a determined reverse-engineer (it's HMAC with an embedded/derived secret, symmetric, app signs and verifies its own stamp). Fine for the stated threat model, but don't oversell it as DRM.
- **Anti-tamper account check depends on a local JSON registry** (`protected_accounts.json`) and the configured keys dir; misconfiguration could either lock out legitimate users or be bypassable. Worth a security review.
- **GitHub-scan path takes a token + downloads a repo at runtime** — the one place the "no egress" property bends (by design, when the user initiates it). Make sure that's clearly scoped and the token isn't logged/persisted.
- **Zip handling**: the SBOM upload path has explicit Zip-Slip protection; confirm the *SAST* zip path (`ScanCreateView`) has equivalent protection before trusting arbitrary uploads (it extracts to a temp dir but the slip guard is less visible there).
- **No automated frontend or integration tests** — only the 91 backend scanner unit tests. End-to-end behavior is verified manually.

---

## 13. Missing documentation

- **No onboarding/dev-environment setup guide** beyond the build scripts — how to run backend + frontend + a local llama-server *for development* (vs. building the full app) isn't written down in one place. (This document partly fills that gap.)
- **No API reference.** The endpoint surface is only discoverable by reading `urls/` + views. An OpenAPI/Swagger spec would help a lot, especially the request/response shapes (which are hand-built, not schema-derived).
- **The data model isn't documented as an ERD.** The loose-FK convention especially needs a written explanation (this doc's §6 is a start).
- **The two licensing systems aren't reconciled in docs** — which is canonical, what the central-server path was for, and whether it's being removed.
- **`.env` documentation is stale and incomplete** — the example file mixes dead Mongo vars with current ones and doesn't explain the build-injected secrets (`LICENSE_SECRET`, `JWT_TOKEN_SECRET`).
- **No CONTRIBUTING / branching / release doc.** Given 70+ unpushed commits and the freeze-swap workflow, the team needs a written release process (the build docs cover packaging mechanics but not the workflow).
- **The eval harness** (`scripts/eval/`) has a BASELINE but no doc on how to interpret thresholds or run it routinely as a quality gate.
- **Frontend has minimal docs** — no component/architecture overview for the React app beyond a stock README.

---

## 14. Recommended next steps

For *you, the new developer*, in order:

**Week 1 — get oriented and running.**
1. Read the §10 files. Skim `docs/superpowers/` specs in date order to absorb the design history.
2. Clone the bundled repo (`git clone codesense-repo.bundle yacm`), create the backend venv, and run the scanner test suite (`cd server && python manage.py test scanner`, expect **91 passing**). This confirms your environment.
3. Stand up a *dev* loop: run the Django backend from source (`run_server.py`/`runserver` on :8585), run the Vite frontend (`bun dev` / `npm run dev` in `client/`), and run a local `llama-server` on :8001 with any small model so the pipeline doesn't error. Do one end-to-end scan of a small repo to watch `queued → in_progress → completed` and see findings appear.
4. Learn the freeze-and-swap loop (per `CLAUDE.md`) so you can verify backend changes in the *packaged* app — you'll need it.

**Immediate housekeeping (coordinate with the team).**
5. Get the **uncommitted 14-file session committed** and the **~70 unpushed commits pushed** to `origin` (needs someone with GitHub creds in a normal terminal — it's blocked in the handoff environment).

**Highest-leverage product work (this is where the roadmap points).**
6. **Resolve the model license (urgent, blocking commercial release).** Confirm `astra.gguf`'s base lineage, get legal sign-off, and commit to moving off the non-commercial 3B. (Next-steps #1, scope doc §9.1.)
7. **Do the instruction-tuned model swap.** This single change fixes *both* the dead verifier and the low enrichment rate, and resolves the license issue. The scope doc estimates ~1–1.5 days of code work; the gist:
   - Convert a chosen **Apache-licensed, instruction-tuned** model to GGUF (recommended ladder: Qwen2.5-Coder-Instruct at 1.5B/7B/14B/32B by device tier; fill the "3B gap" with Qwen3-4B-Instruct or IBM Granite).
   - **De-FIM the LLM client** (`server/scanner/rag/llm.py`): the FIM stop-tokens and `_clean_output()` "Vulnerability:" hunting will mangle clean instruct JSON — gate them off and allow a system prompt.
   - Add **grammar-constrained JSON** (llama.cpp GBNF / `response_format`) to the verifier + reporter so valid JSON is guaranteed.
   - Re-tighten the verifier prompt now that the model can follow instructions.
   - **Validate** with the throwaway scripts in `verification/` (the safe parameterized query must now classify `FP`) and the eval harness thresholds, then re-freeze + swap + re-scan.

**Then, quality and hardening.**
8. **Batch/merge the two LLM calls** per finding to cut scan time (next-steps #3).
9. Add a **migration to persist `confidence` + `verifier_reason`** so the UI can show verdict metadata.
10. **Scrub committed secrets** and require build-time injection for `JWT_TOKEN_SECRET`, `LICENSE_SECRET`, `COSIGN_PASSWORD`; fix the stale `.env.example`.
11. Decide the fate of the **central-server licensing** code (remove or revive) to end the two-systems confusion.
12. Do a clean **distribution build** (`build_macos.sh` / `build_windows.ps1`) — the session verified via in-place swap, not a fresh installer — and re-run the eval baseline as a release gate.

---

*This guide reflects the repository state on branch `lsast-handoff-2026-05-31`. When in doubt, the code and the dated specs in `docs/superpowers/` are authoritative; the `00-SESSION-NARRATIVE.md` explains the most recent changes.*

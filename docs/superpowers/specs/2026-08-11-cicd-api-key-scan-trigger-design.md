# CI/CD scan trigger via project-scoped API keys — Design

2026-08-11. Scoped in a brainstorming session per handoff `09-2026-08-11-vcredist-webview2-cosign-grype-login-fixes-handoff.md`'s "Next priorities" #2 (Azure DevOps CI/CD pipeline support), the first of two SUPER PRIORITY items — this is priority 1 of that pair (incremental scan is priority 2, scoped separately).

## Goal

Let a CI/CD pipeline (Azure DevOps first, but the mechanism is not Azure-DevOps-specific) trigger a real, full Code Sense scan against the code it's building, with the resulting findings persisted and visible in the app exactly like any other scan — no new scan format, no build-gating, fire-and-forget.

## Background (confirmed by code survey this session)

- The scan pipeline (`lsast_scan_folder()` in `server/scanner/rag/lsast_scanner.py`) already runs the full LSAST pipeline — detector (OpenGrep) → finding_normalizer → llm_verifier → fusion → report_enricher → persist — and is triggered today only via two HTTP views: `ScanCreateView` (zip upload) and `GitHubRepoScanView` (repo clone by URL/branch), both in `server/local/api_app/views/scan_views.py`.
- `Project` and `Scan` models (`server/local/api_app/models/orm.py`) already tie every scan to a project and already support scan-history lookup (`ScanModel.find_by_project`).
- Auth today is exclusively human-login bearer JWT: `require_permission` (`server/local/auth_app/permissions/decorators.py:58-84`) decodes a JWT (`server/local/auth_app/utils/jwt.py`), resolves a `role` claim against `PermissionModel`. There is no DRF token auth, no API-key concept, no service-account concept anywhere in `server/`.
- The existing `.github/workflows/lsast-eval-gate.yml` is unrelated prior art — it gates a curated accuracy-eval fixture set, not real project scans.

## Decisions made this session (with rationale)

1. **Build order**: this (CLI/CI-integration) work precedes incremental scan, since any CI integration needs *something* non-interactive to call regardless of shape, making it foundational.
2. **Full pipeline, not detector-only**: CI-triggered scans run the identical full LSAST pipeline (including the LLM verifier/enrichment) that manual scans run — not a stripped CI-speed mode. Rationale: parity with a full scan matters more than CI speed here, and see decision 3.
3. **App does the scanning, not the CI runner**: the CI step calls the app's existing scan-trigger endpoints; the app (wherever it's already running, with its own model host) does the actual work. This sidesteps the real problem of an ephemeral CI runner having no GPU/local LLM host, and mirrors how the client's prior tool (Fortify) structures its own CI integration (a local scan step writes a report artifact; a separate step uploads to the central server; gating is evaluated centrally) — here simplified further since there's no gating requirement.
4. **Results must always land in the app**, visible in the normal UI/scan-history — not a CI-only artifact/report format. This was the user's core, non-negotiable requirement.
5. **New API-key / service-account auth mechanism**, not reuse of a human's JWT. Rationale: a human JWT expires and isn't a real machine identity; embedding a real person's login credential in a pipeline secret is bad practice. This is net-new backend work, scoped narrowly (see Architecture).
6. **Support both code-delivery modes** (zip-upload of the CI's exact checkout, and repo-clone by URL/branch) by reusing both existing endpoints — no new scan-input mechanism, just a new caller of each.
7. **Require an existing `--project-id`**, no auto-create/match-by-name. Keeps API-key scoping unambiguous (a key is bound to exactly one project).
8. **Fire-and-forget**: the pipeline step triggers the scan and does not wait or poll. No build gating, no severity threshold, no exit-code contract tied to findings. This eliminates the need for any report format (SARIF, etc.) or a "gate" concept entirely for this pass.
9. **No new CLI binary**: ship the backend auth mechanism plus a documented pipeline snippet (Azure DevOps YAML: zip + `Invoke-RestMethod` for zip mode, a JSON POST for repo-clone mode) that calls the existing endpoints directly. Rationale: with no gating logic needed, the "CLI" collapses to a couple of HTTP calls — not enough surface to justify a packaged, versioned executable.
10. **Key issuance needs a UI now** (revised from an initial "management-command only" recommendation, per explicit user correction) — a "CI API Keys" panel in project settings, not just a `manage.py` command.
11. **Both deployment topologies must actually work, not just the reachable one** (this was asked for early on — "consider both scenarios" — and the first draft of this spec silently narrowed to only the reachable case while simplifying toward fire-and-forget; corrected here). See "Request flow" below for the mechanism: the zip is always produced as a CI artifact regardless of reachability, and submission to the app is decoupled from that so it can happen immediately (reachable case) or later, from wherever reachability exists (local-only case) — without inventing a new report format or a new endpoint.
12. **A failed *submission* must fail the pipeline step loudly**, even though scan *findings* are still not gated on (decision 8 stands — this is not build-gating). Rationale: fire-and-forget without any failure signal means a revoked key, a network blip, or a misconfigured URL causes CI to silently stop scanning entirely, with nothing surfacing that until someone happens to notice a gap in scan history. Distinguishing "did the code get successfully handed off for scanning" from "what did the scan find" keeps that failure mode visible without reintroducing a findings-based gate.

## Architecture

### New: `APIKey` model

Project-scoped credential, distinct from a user/JWT identity:

- `project` — FK to `Project`
- `name` — human label (e.g. `"azure-devops-prod"`)
- `key_hash` — hash of the key; **plaintext is never persisted**
- `key_prefix` — a short, non-secret prefix (e.g. `csk_`) stored in the clear so keys are visually distinguishable from JWTs and the UI can show a truncated identifier (`csk_a1b2...`) without exposing the secret
- `created_by` — FK to the admin `User` who generated it
- `created_at`, `last_used_at` (nullable, updated on successful auth), `revoked_at` (nullable — revocation sets this rather than deleting the row, preserving audit history)

### Auth path

`require_permission` (or a sibling check invoked before it) inspects the `Authorization: Bearer <token>` header:

- If the token matches the API-key shape (`csk_` prefix) → hash it, look up `APIKey` by `key_hash`, reject (401) if not found or `revoked_at` is set, otherwise stamp a synthetic **service identity** on the request scoped to exactly the `create_scan` permission and exactly that key's bound `project_id`. Update `last_used_at`.
- Otherwise → existing JWT decode/role-permission path, entirely unchanged.

**Project-scoping enforcement**: because a key is bound to one project, `ScanCreateView` and `GitHubRepoScanView` must reject (403) any request where the body's `project_id` doesn't match the authenticated key's bound project. A key for Project A can never trigger a scan into Project B. This check only applies to service (API-key) identities — human JWT callers keep whatever project access their role already grants.

### Key-management endpoints (new, human-JWT-only)

- `POST /api/projects/<id>/api-keys/` — create a key, response includes the **plaintext value exactly once**
- `GET /api/projects/<id>/api-keys/` — list keys for the project (name, prefix, created_at, last_used_at, revoked status) — never returns plaintext or the hash
- `POST /api/projects/<id>/api-keys/<key_id>/revoke/` — set `revoked_at`

All three are gated by human JWT auth under whatever permission already governs other project-settings actions (exact permission slug to be confirmed during planning — an API key must never be usable to mint or manage other API keys, so these three routes explicitly do **not** accept the service-identity auth path at all, regardless of permission scoping).

`manage.py create_api_key --project <id> --name "..."` remains available as a scriptable escape hatch alongside the UI, sharing the same creation logic.

### Frontend: "CI API Keys" panel (project settings)

- **List**: existing keys for the project — name, created date, last-used date, active/revoked status.
- **Generate**: opens a modal showing the plaintext key once, with a copy button and an explicit "you won't be able to see this again" warning (standard pattern — GitHub/Stripe-style token creation UX).
- **Revoke**: per-key action, confirms before revoking.

### Request flow (CI side)

Two supported delivery modes, both unchanged endpoints beyond the new auth layer:

1. **Zip mode**: pipeline step zips its checked-out workspace (e.g. `Compress-Archive` in Azure DevOps YAML) and `POST`s it multipart to `ScanCreateView` with `Authorization: Bearer csk_...` and the bound `project_id`. Scans the pipeline's exact checkout state.
2. **Repo-clone mode**: pipeline step `POST`s a repo URL + branch/commit to `GitHubRepoScanView`, same auth header. The app clones and scans as it already does for a UI-triggered GitHub scan.

Either way: full LSAST pipeline runs as it does today, persists as a normal `Scan` + `Finding` set under the bound `Project`, visible in the app UI as soon as it completes. The endpoint's response confirms the scan was queued/started; the pipeline step does not poll for completion.

**Submission is decoupled from packaging, so the local-only (unreachable) topology is covered without a new format or endpoint** (decision 11). Repo-clone mode already implies reachability (the app has to be able to reach the git host either way) so this fallback is specific to zip mode:

- The CI step **always** zips the workspace and publishes it as a pipeline artifact (e.g. Azure DevOps `PublishPipelineArtifact`), independent of whether the app is reachable. This step has zero network dependency on the app and never fails for reachability reasons.
- **If the app is reachable** from the CI runner (pipeline author sets the app's URL; reachability is just "does the POST succeed"), the same step immediately `POST`s that zip to `ScanCreateView` as described above — this is the common case and needs no extra step.
- **If the app is not reachable** from CI (local-only deployment), the immediate `POST` is skipped and the zip artifact simply sits in the pipeline's artifact store. Submission happens later from wherever reachability *does* exist — a person or a scheduled job on a machine that can reach both the CI artifact store and the app runs the exact same `POST` to `ScanCreateView` with the same API key, at whatever delay. No new "import" endpoint is needed: it's the same zip-upload call, just invoked from a different place at a different time.
- This means the only thing that changes between topologies is *when and from where* the existing endpoint gets called — the endpoint, the auth mechanism, and the persisted result are identical either way.

## Error handling

- Unknown or revoked API key → `401`, same response shape as an invalid JWT today
- `project_id` mismatch (key bound to a different project) → `403`
- Malformed zip / unreachable repo → whatever error path the existing UI-triggered flow already produces (no new error handling needed — this reuses the pipeline as-is)
- **Submission failure must fail the pipeline step (decision 12)**: the documented pipeline snippet treats any non-2xx response from `ScanCreateView`/`GitHubRepoScanView` (401/403/5xx/network error) as a hard step failure — non-zero exit, clear log line naming the cause (e.g. "Code Sense scan submission failed: 401 unauthorized — check the API key"). This is purely about whether the *handoff* succeeded, not about scan findings — a scan that submits successfully and later reports findings still does not fail the build (decision 8 unchanged). The artifact-publish step (always runs, no network dependency) is unaffected by this — only the immediate-submission step in the reachable-topology path can fail this way.

## Testing

- **Auth path**: unit tests for valid key, revoked key, unknown key, malformed `Authorization` header, and wrong-project key (403) — parallel to whatever coverage exists for the JWT path today
- **Key-management endpoints**: create returns plaintext once and never again on subsequent list calls; list never leaks hash/plaintext; revoke sets `revoked_at` and a revoked key subsequently fails auth; permission-gated (a non-admin/unauthorized JWT can't manage keys); a service identity (API key) cannot call these endpoints at all
- **Integration**: a `POST` to `ScanCreateView`/`GitHubRepoScanView` authenticated with a valid API key creates a `Scan` under the correct `Project` and runs the same pipeline as a JWT-authenticated request
- **Management command**: `create_api_key` creates exactly one `APIKey` row; plaintext is only ever printed to stdout, never persisted
- **Frontend**: generate/copy/revoke flow in the CI API Keys panel — plaintext shown once and not recoverable after modal close, revoked keys show correct status
- **Pipeline snippet**: the documented Azure DevOps steps exit non-zero and log a clear cause on a rejected submission (invalid/revoked key, unreachable app), and exit zero on a successful submission regardless of what the scan eventually finds; the artifact-publish step succeeds independent of app reachability

## Explicitly out of scope / deferred (YAGNI)

- Build gating, severity thresholds, pass/fail exit codes on the CI side — no requirement surfaced; fire-and-forget was the explicit call (decision 8)
- SARIF or any CI-native report/annotation format — no requirement surfaced; only relevant if inline PR annotation UX gets asked for later
- Detector-only "fast" mode for CI scans — full pipeline was the explicit call (decision 2); the app owns model-host concerns since it does the scanning
- A packaged/versioned CLI binary — a documented pipeline snippet against the existing endpoints is the v1 deliverable (decision 9); a real CLI or an Azure DevOps Marketplace task can wrap the same API later if adoption friction shows up
- Auto-creating/matching a `Project` from CI — an existing `--project-id` is required (decision 7)

## Open items for the implementation plan

- Exact permission slug to gate the three key-management endpoints (confirm against existing project-settings permission checks in `PermissionModel`)
- Key hashing scheme (e.g. SHA-256 of the full key vs. a slower KDF — likely SHA-256 is sufficient since these are high-entropy generated secrets, not user-chosen passwords, but confirm during planning)
- Where exactly the API-key-vs-JWT branch is inserted relative to `require_permission` (new decorator vs. modifying it in place) — a code-level call, not a design-level one

Code Sense (yacm) — Handoff, 2026-07-30 → 2026-08-03

Picking up work on Code Sense, an offline SAST desktop app (Tauri/Rust shell +
Django/Python backend, frozen with PyInstaller, running fully offline). Read
`CLAUDE.md` at repo root for architecture context (still stale on the
`week6`-branch references — repo has been on a single branch, `main`, since
the previous handoff), then
`docs/handoff/06-2026-07-29-trial-mode-branch-consolidation-client-delivery-handoff.md`
for everything through 2026-07-29, then this file for everything since.

## tl;dr status

- **Repo unchanged at the git level**: `main` tip is still `9cc8e92`, pushed,
  in sync with `origin/main`. Nothing new was committed this session — all
  work below is either (a) uncommitted working-tree changes on top of the
  existing carried-over uncommitted files, or (b) build artifacts under
  `client/src-tauri/target/` and delivery zips outside the repo entirely.
- **The priority bug from this session is fully fixed and verified three
  ways**: SBOM license scanning (via the bundled `grant` tool) was silently
  broken in every packaged build — `grant.exe` was never actually staged in
  `resources/tools/` despite `build_windows.ps1` intending to fetch it.
  Verified via (1) the raw binary with `PATH` fully cleared, (2) the real
  Python pipeline code (`_run_grant`/`_parse_grant_check_results`) with
  `SCANNER_TOOLS_DIR` pointed at the bundle, (3) the user live-testing the
  actual running packaged exe end-to-end and confirming "it works."
- **`scripts/build_windows.ps1` has a permanent fix for this, uncommitted.**
  Root cause: `anchore/grant` publishes no Windows release asset at all
  (confirmed against the live v0.6.8 release — only darwin/linux/deb/rpm).
  The script now builds grant from source instead of trying to download it.
  See "Grant fix in detail" below for two non-obvious gotchas hit along the
  way (a broken cgo toolchain on this host, and `tauri build --no-bundle`
  not refreshing existing staged resources).
- **Two ISec review zips exist on disk**, both with the grant fix baked in,
  differing only in trial/license config — see table below. **Open
  question, not yet resolved**: whether to delete the older one.
- **A real, verified client-demo repo recommendation**: OWASP `railsgoat`
  (Ruby/Rails HR app) — live-scanned with the actual bundled detector +
  privacy/secrets rule packs, 35 real findings including 8 hardcoded SSNs
  and PII-logging exposure. Full detail below; no code changes from this.
- **`main.rs` currently has UNCOMMITTED, ISec-build-specific config changes
  sitting in the working tree right now** (`TRIAL_MODE="false"`,
  `LICENSE_DURATION_DAYS="180"`, was `"true"`/`"30"` on committed `main`).
  **Read the warning under "Uncommitted state" before building anything for
  an actual client** — building from the working tree as-is right now would
  ship the unrestricted ISec config, not the intended 2-scan/30-day trial
  config that's actually committed on `main`.

## The SBOM license (`grant`) bug — full detail

**Symptom reported**: packaged exe's SBOM scans showed vulnerability
findings (via `grype`) but zero license findings (via `grant`); the dev/web
instance showed both correctly.

**Root cause**: `tool_path()` in `server/scanner/services/tools.py` resolves
a bundled tool via `SCANNER_TOOLS_DIR`, falling back to the bare command name
(PATH lookup) only if the bundled file doesn't exist. The dev instance has no
`SCANNER_TOOLS_DIR` set, so it always fell through to PATH — and this dev
machine happens to have a self-built `C:\grant\grant.exe` on PATH (unrelated
to the packaged app). The packaged exe pins `SCANNER_TOOLS_DIR` to
`resources/tools/`, which never actually had `grant.exe` in it — `syft`,
`grype`, `cosign`, `semgrep` were all staged correctly, `grant` silently
wasn't. The failure is swallowed by a broad `except Exception: print(...)` in
`server/scanner/services/sbom_pipeline.py`'s `_run_grant()` call sites, so it
never surfaced as a visible error anywhere in the app.

**Why `grant` specifically was never staged**: `scripts/build_windows.ps1`
fetched syft/grype/grant identically — `Get-GhAsset "anchore/$tool"
"_windows_amd64\.zip$"` — but `anchore/grant`'s GitHub releases only publish
darwin/linux/deb/rpm assets, never a Windows zip. A real run of the old
script would have `Die`d on this step; the staged `resources/tools/` this
session found had 4 of 5 tools (missing exactly `grant.exe`), suggesting a
past session worked around the `Die` by hand (building grant from source
locally into `C:\grant`) without ever copying the result into the bundle.

**Fix, in three layers:**
1. **Immediate (unblocks the already-built exe)**: copied the working
   `C:\grant\grant.exe` into `client/src-tauri/target/release/resources/tools/`
   (and `target/debug/`'s). Verified with `PATH` fully cleared.
2. **Permanent, in `scripts/build_windows.ps1` (uncommitted)**: `grant` is
   pulled out of the syft/grype download loop; a new block `git clone`s a
   pinned tag of `anchore/grant` and `go build`s `./cmd/grant`. Two gotchas
   hit getting here, both resolved:
   - Tried `"latest"` (`v0.6.8`) first — its `go.mod` requires `go 1.26.3`,
     which forced a toolchain auto-download, and even that toolchain's own
     `cgo.exe` failed compiling the **standard library's own** `runtime/cgo`
     package with no useful diagnostic (`exit status 2`, nothing more).
     Isolated with a trivial hello-world cgo test: the *already-installed*
     Go 1.25.2 toolchain's `cgo.exe` fails the exact same way on this host —
     this is a genuine cgo/gcc environment problem on this machine,
     unrelated to grant or its version. Not investigated further (out of
     scope); worked around instead.
   - Fix: build with `CGO_ENABLED=0` (grant's sqlite driver is the pure-Go
     `modernc.org/sqlite`, so it doesn't actually need cgo) **and** pin the
     tag to `v0.5.7` instead of latest — its `go.mod` only needs `go 1.24.6`
     and has a far smaller dependency graph (v0.6.8 vendors syft as a
     library, ~150+ transitive deps including AWS/GCP SDKs). Comment in the
     script explains both and says to only bump the pin after confirming
     `CGO_ENABLED=0 go build ./cmd/grant` succeeds on the actual build host
     first.
   - **New gotcha, worth remembering**: `npx tauri build --no-bundle` does
     **not** refresh resource files that already exist in
     `target/release/resources/` — only copies files that are missing. After
     rebuilding, `target/release/resources/tools/grant.exe` still had the old
     158MB dev-build copy even though the source tree had a fresh 81MB
     `CGO_ENABLED=0` build. Had to manually re-copy after every
     `tauri build --no-bundle`. Anyone changing a bundled tool binary needs
     to do the same until this is scripted (build_windows.ps1's own
     resource-staging happens before the tauri build in the full pipeline,
     which is presumably why this was never hit before).
3. **Verified three separate ways** (raw binary, real Python pipeline code,
   live app + user confirmation) — see tl;dr above.

`scripts/build_windows.ps1` was syntax-checked (`Parser]::ParseFile`, no
errors) and BOM-checked (still UTF-8 with BOM — the file has broken before
from em-dash/BOM issues, see `CLAUDE.md`'s Windows/PS5.1 gotchas) after every
edit.

## ISec review zips

Both built from `client/src-tauri/target/release/` (root exe/dlls +
`resources/{model,grype-db,tools,semgrep-rules}/` + `README-ISEC.txt`,
zipped with `System.IO.Compression` at `NoCompression`, excluding
`target/release/license_data/` per established convention). Both verified
byte-exact against source via SHA256 on several spot-checked entries
(root exes, `README-ISEC.txt`, `resources/tools/grant.exe`, a model shard).
Both have the grant fix baked in.

| File | Trial cap | License | Entries | Size |
|---|---|---|---|---|
| `C:\Users\AstraCybertech\codesense-v1\codesense-isec-build-2026-07-30.zip` | 2 scans, shared code+SBOM | 30 days | 4062 | ~7.23 GB |
| `C:\Users\AstraCybertech\codesense-v1\codesense-isec-build-2026-07-30b.zip` | **none — unlimited** | **180 days** | 4062 | ~7.23 GB |

The `b` build required editing `main.rs`'s `TRIAL_MODE`/`LICENSE_DURATION_DAYS`
constants (see "Uncommitted state" below), then a full `tauri build
--no-bundle` + manual grant.exe re-copy + fresh zip. Config was confirmed
**live** before zipping — launched the actual rebuilt exe and hit its real
API: `/api/trial/` → `{"trial_mode":false,"limit":null,...}`,
`/api/license/` → `expires_at: 2026-12-28, days_remaining: 150` (proof the
180-day window is really applied — the old 30-day value would already show
this license as expired given the existing `first_seen` timestamp in this
machine's app data from earlier testing).

`README-ISEC.txt` (lives only in `target/release/`, untracked build output,
not committed — expected) was updated to describe both the grant fix and,
in the `b` build, the disabled trial cap / 180-day license.

**Open, unresolved**: user was asked whether to delete the older `a` zip
(2-scan/30-day) now that `b` supersedes it for review purposes — never
answered. Both are still on disk. Also on disk, unexplained and untouched:
`C:\Users\AstraCybertech\codesense-v1\quick_scan_test.zip` (439 bytes, a
minimal `app.py`+`requirements.txt` test fixture zip — not created this
session, likely leftover from earlier upload testing).

The two zips from the *previous* handoff
(`codesense-isec-build-2026-07-28c.zip`,
`codesense-client-trial-2026-07-29.zip`) are still not on disk anywhere.
User was asked again this session whether they'd already been sent and
explicitly said to ignore the question — **do not re-ask this in a future
session**, treat it as closed/not worth chasing.

## Client-demo repo verification (no code changes, informational)

User asked for a "legit repo" to demo PIA/hardcoded-secret detection to a
client. Recommended **OWASP `railsgoat`** (`github.com/OWASP/railsgoat`, a
Ruby/Rails HR-payroll app deliberately built around insecure PII handling)
and verified it live rather than guessing: cloned fresh, ran the actual
bundled OpenGrep binary with `--config` pointed at the privacy rule pack +
the bundled `generic/secrets` pack + `ruby/lang/security`, against a copy of
the repo with `.git` stripped (OpenGrep's known git-working-tree walker bug,
see `CLAUDE.md`).

**Result: 35 real findings**, incl. 16 `ruby-pii-logging-exposure`, 8
`hardcoded-ssn-literal` (real hardcoded SSNs in `db/seeds.rb` /
`config/initializers/populate_user_data.rb`), 1 `detected-generic-api-key`,
4 `weak-hashes-md5`, plus CSRF/mass-assignment/deserialization findings.
**One caveat surfaced and flagged to the user**: the 3
`hardcoded-credit-card-literal` hits are false positives — CSS percentage
values in `main.css.erb` coincidentally matching the raw regex (no dataflow
context in that rule). Framed to the user as a good thing to demo
*intentionally* — the full pipeline's LLM verifier stage should suppress
these, showing off FP suppression rather than hiding the rough edge.
No Aadhaar/PAN hits (railsgoat is US-context) — flagged as a gap if the
client specifically wants the India govt-ID rules demonstrated.

## Uncommitted state — READ BEFORE BUILDING ANYTHING FOR A REAL CLIENT

`git status --short` on `main` right now:

```
 M client/src-tauri/.gitignore
 M client/src-tauri/src/main.rs          <-- see warning below
 M client/src-tauri/tauri.conf.json
 M client/src/hooks/use-asset-setup.test.ts
 M client/src/hooks/use-asset-setup.ts
 M docs/RELEASE-NOTES.md
 M scripts/build_windows.ps1             <-- the grant fix, see above
 M server/run_dev.ps1
?? app_stderr.log
?? app_stdout.log
?? client/.env.development
?? docs/handoff/06-...-handoff.md        <-- previous handoff, never committed
?? server/local/api_app/views/.gitignore
```

**`main.rs` currently reads `TRIAL_MODE="false"` / `LICENSE_DURATION_DAYS="180"`
— this is the ISec-review config, not what's committed on `main` (which is
`"true"`/`"2"`/`"30"`, from commit `9cc8e92`, meant for actual client trial
deliveries).** Building a real client-delivery zip from the working tree
right now, without reverting these two lines first, would ship the
unrestricted review config to a paying/trial client by mistake. Revert with:
```
git checkout -- client/src-tauri/src/main.rs
```
(safe — the only diff on that file this session was these two constants)
before any client-facing (non-ISec) build.

The rest of the modified/untracked list — `tauri.conf.json`, `.gitignore`,
`use-asset-setup.ts`/`.test.ts`, `RELEASE-NOTES.md`, `run_dev.ps1`,
`app_std{out,err}.log`, `client/.env.development`,
`server/local/api_app/views/.gitignore` — is the same **pre-existing,
carried-over-across-many-sessions** set from every prior handoff; still
undecided, still untouched this session, still don't touch without asking.
`scripts/build_windows.ps1`'s diff is exactly the grant fix described above
and is safe/intended to keep. The untracked
`docs/handoff/06-...-handoff.md` is the *previous* session's own handoff
file, apparently never committed — worth committing at some point along
with this one, but not done unilaterally.

## Next steps / open items

1. Decide + commit (or discard) the long-carried "don't touch without
   asking" files — same item as every prior handoff, still open.
2. Decide whether to keep `main.rs` reverted to committed values by default,
   or find a cleaner way to parameterize trial/license config per build
   target (env var / build flag) instead of hand-editing constants each time
   — this session hit the exact risk that motivates that (an ISec-only
   config change sitting uncommitted, one accidental build away from
   shipping to the wrong audience).
3. Resolve whether to delete the older `codesense-isec-build-2026-07-30.zip`
   now that `b` (unrestricted/180-day) supersedes it for review purposes.
4. `scripts/build_windows.ps1`'s grant fix (`CGO_ENABLED=0`, pinned
   `v0.5.7`) has not been proven via an actual **from-scratch, full**
   `build_windows.ps1` run (no `-SkipTools`) — this session only ran the
   grant-specific `git clone` + `go build` steps in isolation, not the whole
   script end-to-end. Worth a real full run before trusting it blindly next
   time a client build is needed from zero.
5. The underlying host cgo/gcc breakage (even the pre-installed Go
   toolchain's `cgo.exe` fails on a trivial hello-world) was worked around,
   not fixed. If a future task genuinely needs cgo on this machine (e.g. a
   dependency without a pure-Go fallback), that'll need real investigation.
6. If the client specifically wants India govt-ID (Aadhaar/PAN) rule hits
   demonstrated, `railsgoat` won't show it (US-context repo) — would need a
   different repo or a small added fixture.
7. Carried from the 06 handoff, still open: `githubrepo.tsx`'s non-functional
   SBOM scan-type option (low priority); the rule-id garbling display bug.

## How to apply this handoff

Read `CLAUDE.md`, then `docs/handoff/06-...-handoff.md`, then this file.
Repo is at `C:\Users\AstraCybertech\codesense-v1\yacm`, single branch `main`,
tip `9cc8e92`, fully pushed — but **check `git status` before touching
anything**, the working tree has real uncommitted state (see above),
especially the `main.rs` trial/license config trap.

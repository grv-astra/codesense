# Scan Interrupt Handling & Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an interrupted (crashed, cancelled, or transiently-failed) code scan be manually
resumed without re-running the expensive per-finding LLM verification for findings already
persisted, and make findings/progress visible live instead of only at scan completion.

**Architecture:** Give every raw detector finding a stable fingerprint (file + line + rule id).
Persist findings as each one finishes its LLM call, not after the whole batch drains. Retain the
extracted source on disk instead of deleting it unconditionally. On any non-`completed` outcome,
the scan lands in `"interrupted"` or `"cancelled"` (both resumable) instead of `"failed"`. Two new
endpoints (`resume`, `cancel`) plus a startup reconciliation pass in `run_server.py` are the only
new surface area — everything else reuses the existing LSAST pipeline shape.

**Tech Stack:** Django (SQLite via the existing ORM models), Python `concurrent.futures`,
`threading`, DRF (`rest_framework`) views. No new dependencies.

**Spec:** [docs/superpowers/specs/2026-08-04-scan-interrupt-resume-design.md](../specs/2026-08-04-scan-interrupt-resume-design.md)

---

## File Structure

**New files:**
- `server/local/api_app/migrations/0006_scan_resume_fields.py` — adds `Scan.source_path`,
  `Scan.cancel_requested`, `Finding.fingerprint`.
- `server/scanner/rag/resume.py` — pure fingerprint/checkpoint logic: `fingerprint()`,
  `already_done_fingerprints()`, `find_orphaned_scans()`, `reconcile_orphaned_scans()`. No view or
  pipeline code — kept isolated so it's trivially unit-testable and has no framework-request
  dependency.
- `server/scanner/rag/tests/test_resume.py` — unit tests for the above.

**Modified files:**
- `server/local/api_app/models/orm.py` — new fields on `Scan`/`Finding`.
- `server/local/api_app/models/finding_models.py` — `fingerprint` added to the persisted-field
  allowlist (`_FIELDS`).
- `server/scanner/rag/lsast_scanner.py` — fingerprint attached per finding; `skip_fingerprints`
  filtering; persist-as-you-go instead of batch-at-the-end; cooperative cancel check.
- `server/scanner/rag/scanner.py` — passes `skip_fingerprints`/`cancel_event` through; AST-failure
  and cancel outcomes use the new statuses instead of `"failed"`/`"completed"`.
- `server/local/api_app/views/scan_views.py` — durable extraction path; shared
  `_run_lsast_pipeline()` helper (replaces the duplicated thread-body logic); new `ScanResumeView`,
  `ScanCancelView`; module-level cancel-event registry.
- `server/local/api_app/urls/scan_urls.py` — routes for the two new views.
- `server/run_server.py` — one call to `reconcile_orphaned_scans()` at startup.
- `server/licenses/services/trial.py` — `interrupted` joins the set of statuses counted against the
  trial cap; `cancelled` deliberately does not.
- `server/scanner/tests/test_lsast_scanner.py` — new tests for skip-filtering, live persistence
  timing, and cancel.
- `server/scanner/tests/test_scanner.py` — new tests for the AST-failure status change and the
  cancel-detected-after-loop path.
- `server/local/api_app/tests/test_scan_views.py` — new tests for the durable path, resume, and
  cancel endpoints.
- `server/local/api_app/tests/test_trial.py` — new tests for `interrupted`/`cancelled` trial
  accounting.

---

### Task 1: Migration — add the three new fields

**Files:**
- Modify: `server/local/api_app/models/orm.py`
- Create: `server/local/api_app/migrations/0006_scan_resume_fields.py`

- [ ] **Step 1: Add the fields to the models**

In `server/local/api_app/models/orm.py`, add to the `Scan` class (after the existing `metrics`
field, before `class Meta:`):

```python
    source_path = models.CharField(max_length=1024, blank=True, default="")
    cancel_requested = models.BooleanField(default=False)
```

Add to the `Finding` class (after `code_snip_start_line`, before `class Meta:`):

```python
    # Stable identity for the raw detector match this Finding came from
    # (sha256 of file_path+start_line+rule_id) -- lets a resumed scan tell
    # which findings were already verified+persisted in a prior attempt and
    # skip re-running the LLM step for them. Blank for pre-existing rows.
    fingerprint = models.CharField(max_length=64, blank=True, default="", db_index=True)
```

- [ ] **Step 2: Generate the migration**

Run: `cd server && .venv/Scripts/python.exe manage.py makemigrations api_app`
Expected output includes:
```
Migrations for 'api_app':
  local\api_app\migrations\0006_scan_resume_fields.py
    - Add field cancel_requested to scan
    - Add field source_path to scan
    - Add field fingerprint to finding
```

If Django names the file differently, rename it to `0006_scan_resume_fields.py` for a predictable
name the rest of this plan can reference (the exact operations inside are what matter, not the
filename Django picks).

- [ ] **Step 3: Verify the migration applies cleanly**

Run: `cd server && .venv/Scripts/python.exe manage.py migrate api_app`
Expected: `Applying api_app.0006_scan_resume_fields... OK`

- [ ] **Step 4: Commit**

```bash
git add server/local/api_app/models/orm.py server/local/api_app/migrations/0006_scan_resume_fields.py
git commit -m "feat(scan): add source_path/cancel_requested/fingerprint fields for resume"
```

---

### Task 2: `resume.py` — `fingerprint()`

**Files:**
- Create: `server/scanner/rag/resume.py`
- Create: `server/scanner/tests/test_resume.py`

- [ ] **Step 1: Write the failing test**

```python
# server/scanner/tests/test_resume.py
from django.test import SimpleTestCase

from scanner.rag.lsast_types import SemgrepFinding
from scanner.rag.resume import fingerprint


def _finding(**overrides) -> SemgrepFinding:
    base = dict(
        rule_id="python.lang.security.audit.sql-injection.tainted-sql-string",
        cwe="CWE-89", severity="high", message="Possible SQL injection",
        file_path="app/views.py", start_line=12, end_line=18,
        code_excerpt="cursor.execute(query)",
    )
    base.update(overrides)
    return SemgrepFinding(**base)


class FingerprintTests(SimpleTestCase):
    def test_same_finding_same_fingerprint(self):
        self.assertEqual(fingerprint(_finding()), fingerprint(_finding()))

    def test_different_line_different_fingerprint(self):
        self.assertNotEqual(fingerprint(_finding()), fingerprint(_finding(start_line=99)))

    def test_different_rule_id_different_fingerprint(self):
        self.assertNotEqual(fingerprint(_finding()), fingerprint(_finding(rule_id="other-rule")))

    def test_different_file_path_different_fingerprint(self):
        self.assertNotEqual(fingerprint(_finding()), fingerprint(_finding(file_path="app/other.py")))

    def test_message_and_severity_do_not_affect_fingerprint(self):
        # A rules-pack wording tweak shouldn't invalidate an existing checkpoint.
        self.assertEqual(
            fingerprint(_finding()),
            fingerprint(_finding(message="different wording", severity="critical")),
        )

    def test_fingerprint_is_a_64char_hex_string(self):
        fp = fingerprint(_finding())
        self.assertEqual(len(fp), 64)
        int(fp, 16)  # raises ValueError if not valid hex
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_resume -v 2`
Expected: FAIL with `ModuleNotFoundError: No module named 'scanner.rag.resume'`

- [ ] **Step 3: Write the implementation**

```python
# server/scanner/rag/resume.py
"""Resume/checkpoint support for interrupted LSAST scans.

A "fingerprint" identifies one raw Semgrep finding independent of message/
severity wording, so a resumed run can tell which findings were already
verified+persisted in a prior attempt and skip re-running the expensive LLM
step for them.
"""
from __future__ import annotations

import hashlib

from scanner.rag.lsast_types import SemgrepFinding


def fingerprint(sf: SemgrepFinding) -> str:
    """Stable identity for one raw detector finding: file + line + rule.

    Deliberately independent of message/severity/CWE text (a rules-pack
    wording update shouldn't invalidate an existing checkpoint) -- file_path +
    start_line + rule_id is what actually identifies "the same match" across
    two detector runs over the same source.
    """
    raw = f"{sf.file_path}:{sf.start_line}:{sf.rule_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_resume -v 2`
Expected: `OK` (6 tests)

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/resume.py server/scanner/tests/test_resume.py
git commit -m "feat(scanner): add fingerprint() for resume checkpointing"
```

---

### Task 3: `resume.py` — `already_done_fingerprints()`

**Files:**
- Modify: `server/scanner/rag/resume.py`
- Modify: `server/scanner/tests/test_resume.py`

- [ ] **Step 1: Write the failing test**

Append to `server/scanner/tests/test_resume.py`:

```python
from datetime import datetime, timezone

from django.test import TestCase

from local.api_app.models.orm import Finding
from scanner.rag.resume import already_done_fingerprints


class AlreadyDoneFingerprintsTests(TestCase):
    def _make_finding(self, scan_id, fp):
        Finding.objects.create(
            scan_id=scan_id, fingerprint=fp, created_at=datetime.now(timezone.utc),
        )

    def test_returns_fingerprints_for_this_scan_only(self):
        self._make_finding("scan-1", "fp-a")
        self._make_finding("scan-1", "fp-b")
        self._make_finding("scan-2", "fp-c")  # different scan, must not appear
        self.assertEqual(already_done_fingerprints("scan-1"), frozenset({"fp-a", "fp-b"}))

    def test_ignores_blank_fingerprints(self):
        # Pre-existing rows from before this feature have fingerprint="".
        self._make_finding("scan-1", "")
        self._make_finding("scan-1", "fp-a")
        self.assertEqual(already_done_fingerprints("scan-1"), frozenset({"fp-a"}))

    def test_empty_for_unknown_scan(self):
        self.assertEqual(already_done_fingerprints("no-such-scan"), frozenset())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_resume -v 2`
Expected: FAIL with `ImportError: cannot import name 'already_done_fingerprints'`

- [ ] **Step 3: Write the implementation**

Add to `server/scanner/rag/resume.py` (after the imports, add `Finding` import; add the function
after `fingerprint()`):

```python
from local.api_app.models.orm import Finding, Scan
```

```python
def already_done_fingerprints(scan_id: str) -> frozenset[str]:
    """Fingerprints already persisted for this scan -- what a resume should skip."""
    return frozenset(
        Finding.objects.filter(scan_id=scan_id)
        .exclude(fingerprint="")
        .values_list("fingerprint", flat=True)
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_resume -v 2`
Expected: `OK` (9 tests)

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/resume.py server/scanner/tests/test_resume.py
git commit -m "feat(scanner): add already_done_fingerprints() for resume filtering"
```

---

### Task 4: `resume.py` — `find_orphaned_scans()` and `reconcile_orphaned_scans()`

**Files:**
- Modify: `server/scanner/rag/resume.py`
- Modify: `server/scanner/tests/test_resume.py`

- [ ] **Step 1: Write the failing test**

Append to `server/scanner/tests/test_resume.py`:

```python
from local.api_app.models.orm import Scan
from scanner.rag.resume import find_orphaned_scans, reconcile_orphaned_scans


def _make_scan(status, cancel_requested=False, deleted=False, **kw):
    return Scan.objects.create(
        project_id="p1", scan_name=kw.get("scan_name", "s"), status=status,
        created_at=datetime.now(timezone.utc), deleted=deleted,
        cancel_requested=cancel_requested,
    )


class FindOrphanedScansTests(TestCase):
    def test_finds_queued_and_in_progress(self):
        a = _make_scan("queued")
        b = _make_scan("in_progress")
        _make_scan("completed")
        _make_scan("failed")
        _make_scan("interrupted")
        _make_scan("cancelled")
        ids = {s.id for s in find_orphaned_scans()}
        self.assertEqual(ids, {a.id, b.id})

    def test_excludes_deleted_rows(self):
        _make_scan("in_progress", deleted=True)
        self.assertEqual(list(find_orphaned_scans()), [])


class ReconcileOrphanedScansTests(TestCase):
    def test_relabels_to_interrupted_by_default(self):
        s = _make_scan("in_progress")
        count = reconcile_orphaned_scans()
        self.assertEqual(count, 1)
        s.refresh_from_db()
        self.assertEqual(s.status, "interrupted")

    def test_relabels_to_cancelled_when_cancel_was_requested(self):
        s = _make_scan("in_progress", cancel_requested=True)
        reconcile_orphaned_scans()
        s.refresh_from_db()
        self.assertEqual(s.status, "cancelled")

    def test_returns_zero_when_nothing_orphaned(self):
        _make_scan("completed")
        self.assertEqual(reconcile_orphaned_scans(), 0)

    def test_does_not_touch_already_terminal_rows(self):
        s = _make_scan("completed")
        reconcile_orphaned_scans()
        s.refresh_from_db()
        self.assertEqual(s.status, "completed")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_resume -v 2`
Expected: FAIL with `ImportError: cannot import name 'find_orphaned_scans'`

- [ ] **Step 3: Write the implementation**

Add to `server/scanner/rag/resume.py` (after `already_done_fingerprints`):

```python
def find_orphaned_scans():
    """Scans still queued/in_progress -- by construction, crash leftovers from a
    prior process (a fresh process hasn't started anything itself yet), unless
    it's this same call's own reconciliation running twice -- callers should
    only invoke this once, at real server startup (see run_server.py)."""
    return Scan.objects.filter(status__in=["queued", "in_progress"], deleted=False)


def reconcile_orphaned_scans() -> int:
    """Relabel crash-orphaned scan rows so the UI reflects reality instead of a
    permanently-stuck "queued"/"in_progress". Source/findings are left exactly
    as they were -- this only changes the status label. Returns how many rows
    were reconciled."""
    count = 0
    for scan in find_orphaned_scans():
        new_status = "cancelled" if scan.cancel_requested else "interrupted"
        Scan.objects.filter(id=scan.id).update(status=new_status)
        count += 1
    return count
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_resume -v 2`
Expected: `OK` (13 tests)

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/resume.py server/scanner/tests/test_resume.py
git commit -m "feat(scanner): add orphaned-scan detection + reconciliation"
```

---

### Task 5: Persist `fingerprint` — allow it through `FindingModel.insert_many`

**Files:**
- Modify: `server/local/api_app/models/finding_models.py`
- Modify: `server/local/api_app/tests/test_finding_model.py`

- [ ] **Step 1: Write the failing test**

Read `server/local/api_app/tests/test_finding_model.py` first to match its existing fixture style,
then add:

```python
def test_insert_many_persists_fingerprint(self):
    from datetime import datetime, timezone
    from local.api_app.models.finding_models import FindingModel
    saved = FindingModel.insert_many([{
        "scan_id": "s1", "title": "t", "cwe": "CWE-89", "severity": "high",
        "status": "open", "created_at": datetime.now(timezone.utc),
        "fingerprint": "abc123",
    }])
    self.assertEqual(saved[0]["fingerprint"], "abc123")
```

(Add this as a method on whichever `TestCase` class the file already uses for `insert_many`
coverage -- follow the existing class/imports rather than creating a new file.)

Note: this test also requires `fingerprint` to appear in `FindingModel.serialize()`'s output (used
here via `saved[0]["fingerprint"]`) -- Step 3 adds both.

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && .venv/Scripts/python.exe manage.py test local.api_app.tests.test_finding_model -v 2`
Expected: FAIL with `KeyError: 'fingerprint'`

- [ ] **Step 3: Write the implementation**

In `server/local/api_app/models/finding_models.py`, add `"fingerprint"` to the `_FIELDS` list:

```python
_FIELDS = [
    "scan_id", "created_by", "cwe", "cvss_vector", "cvss_score", "code", "title",
    "description", "severity", "file_path", "code_snip", "security_risk",
    "mitigation", "status", "deleted", "approved", "reference", "created_at",
    "rule_id", "confidence", "verifier_reason", "flow_diagram", "code_snip_start_line",
    "fingerprint",
]
```

And add to `FindingModel.serialize()`'s returned dict (after `code_snip_start_line`):

```python
            "fingerprint": finding.fingerprint or "",
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test local.api_app.tests.test_finding_model -v 2`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add server/local/api_app/models/finding_models.py server/local/api_app/tests/test_finding_model.py
git commit -m "feat(findings): persist and expose the resume fingerprint"
```

---

### Task 6: `lsast_scanner.py` — attach `fingerprint` to every processed finding

**Files:**
- Modify: `server/scanner/rag/lsast_scanner.py`
- Modify: `server/scanner/tests/test_lsast_scanner.py`

- [ ] **Step 1: Write the failing test**

Add to `server/scanner/tests/test_lsast_scanner.py`, inside `class ProcessOneTests`:

```python
    @mock.patch("scanner.rag.lsast_scanner.generate_report", return_value=None)
    @mock.patch("scanner.rag.lsast_scanner.verify",
                return_value=VerifierVerdict("TP", "unsanitized concat", 0.9))
    def test_outcome_carries_a_fingerprint(self, _v, _g):
        from scanner.rag.lsast_scanner import _process_one
        from scanner.rag.resume import fingerprint
        sf = _sqli_finding()
        outcome = _process_one(sf, "s1", "u1")
        self.assertEqual(outcome.finding["fingerprint"], fingerprint(sf))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_lsast_scanner.ProcessOneTests.test_outcome_carries_a_fingerprint -v 2`
Expected: FAIL with `KeyError: 'fingerprint'`

- [ ] **Step 3: Write the implementation**

In `server/scanner/rag/lsast_scanner.py`, add the import (near the other `scanner.rag.*` imports):

```python
from scanner.rag.resume import fingerprint
```

In `_process_one()`, right after the `finding_dict, dataflow = normalize(...)` line, add:

```python
        finding_dict["fingerprint"] = fingerprint(sf)
```

So the block reads:

```python
    try:
        finding_dict, dataflow = normalize(sf, scan_id=scan_id, triggered_by=triggered_by)
        finding_dict["fingerprint"] = fingerprint(sf)
        if llm_ok:
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_lsast_scanner -v 2`
Expected: `OK` (all existing tests in this file still pass, plus the new one)

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/lsast_scanner.py server/scanner/tests/test_lsast_scanner.py
git commit -m "feat(scanner): attach the resume fingerprint to every processed finding"
```

---

### Task 7: `lsast_scanner.py` — `skip_fingerprints` filtering

**Files:**
- Modify: `server/scanner/rag/lsast_scanner.py`
- Modify: `server/scanner/tests/test_lsast_scanner.py`

- [ ] **Step 1: Write the failing test**

Add to `server/scanner/tests/test_lsast_scanner.py`, inside `class LsastScanFolderTests`:

```python
    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_skip_fingerprints_excludes_already_done_findings(self, mock_run, mock_verify, mock_save):
        from scanner.rag.resume import fingerprint
        done = _sqli_finding()      # pretend this one was already processed
        pending = _safe_orm_finding()
        mock_run.return_value = [done, pending]
        mock_verify.return_value = VerifierVerdict("TP", "x", 0.8)

        visible, filtered = lsast_scan_folder(
            "/tmp/code", "s1", "user-1",
            skip_fingerprints=frozenset({fingerprint(done)}),
        )
        # Only the pending finding should have gone through verify/persist.
        mock_verify.assert_called_once()
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["fingerprint"], fingerprint(pending))

    @mock.patch("scanner.rag.lsast_scanner.save_findings_to_db")
    @mock.patch("scanner.rag.lsast_scanner.verify")
    @mock.patch("scanner.rag.lsast_scanner.run_semgrep")
    def test_skip_fingerprints_matching_everything_short_circuits(self, mock_run, mock_verify, mock_save):
        from scanner.rag.resume import fingerprint
        done = _sqli_finding()
        mock_run.return_value = [done]

        visible, filtered = lsast_scan_folder(
            "/tmp/code", "s1", "user-1",
            skip_fingerprints=frozenset({fingerprint(done)}),
        )
        self.assertEqual((visible, filtered), ([], []))
        mock_verify.assert_not_called()
        mock_save.assert_not_called()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_lsast_scanner.LsastScanFolderTests.test_skip_fingerprints_excludes_already_done_findings -v 2`
Expected: FAIL with `TypeError: lsast_scan_folder() got an unexpected keyword argument 'skip_fingerprints'`

- [ ] **Step 3: Write the implementation**

In `server/scanner/rag/lsast_scanner.py`, change the `lsast_scan_folder` signature and add the
filter step right after `dedupe_findings`:

```python
def lsast_scan_folder(folder_path: str, scan_id: str, triggered_by: str,
                       skip_fingerprints: frozenset[str] = frozenset(),
                       cancel_event=None,
                      ) -> tuple[list[dict], list[dict]]:
    """Run the full LSAST pipeline. Returns (visible, filtered).

    ``skip_fingerprints`` excludes findings already verified+persisted in a
    prior (crashed/cancelled) attempt at this same scan -- see resume.py.
    ``cancel_event``, when set, is checked between findings so a user-requested
    cancel stops the batch promptly instead of running it to completion.
    """
    sem_findings = run_semgrep(folder_path)
    if not sem_findings:
        logger.info("LSAST: Semgrep produced no findings for %s", folder_path)
        return [], []

    raw_count = len(sem_findings)
    sem_findings = dedupe_findings(sem_findings)
    if len(sem_findings) != raw_count:
        logger.info("LSAST: de-duplicated %d -> %d findings", raw_count, len(sem_findings))

    if skip_fingerprints:
        before = len(sem_findings)
        sem_findings = [sf for sf in sem_findings if fingerprint(sf) not in skip_fingerprints]
        logger.info("LSAST: resume filtered %d -> %d findings (already processed)",
                    before, len(sem_findings))
        if not sem_findings:
            logger.info("LSAST: nothing left to process for %s (resume already complete)",
                        folder_path)
            return [], []
```

(The rest of the function body — the `llm_health()` check onward — is unchanged by this task; the
persist-loop restructuring happens in Task 8.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_lsast_scanner -v 2`
Expected: `OK` (all tests, including both new ones)

- [ ] **Step 5: Commit**

```bash
git add server/scanner/rag/lsast_scanner.py server/scanner/tests/test_lsast_scanner.py
git commit -m "feat(scanner): filter already-processed findings on resume"
```

---

### Task 8: `lsast_scanner.py` — persist-as-you-go, live progress, cooperative cancel

This is the core behavioral change: findings currently only get saved after the *entire* batch of
LLM calls finishes. This task makes each finding persist the moment it's ready, updates progress
continuously, and lets a cancel request stop the batch early instead of running it to completion.

**Files:**
- Modify: `server/scanner/rag/lsast_scanner.py`
- Modify: `server/scanner/tests/test_lsast_scanner.py`

- [ ] **Step 1: Write the failing test — findings persist before the batch finishes**

Add to `server/scanner/tests/test_lsast_scanner.py`, inside `class ParallelIdentityTests`:

```python
    def test_finding_persists_before_the_whole_batch_finishes(self):
        """Proves progressive persistence: a fast finding's save() call must
        happen while a slower finding (still running in another worker) hasn't
        returned yet. This fails on the old `list(ex.map(...))` code, which
        blocks persistence until every finding is done."""
        import threading
        slow_release = threading.Event()
        fast_saved = threading.Event()

        def _verify_variable_speed(**kw):
            if kw["code_excerpt"] == "e1":          # the "a" finding: fast
                result = _verify_by_excerpt(**kw)
                return result
            slow_release.wait(timeout=5)             # everything else: blocks
            return _verify_by_excerpt(**kw)

        saved_order = []

        def _tracking_save(findings):
            saved_order.append(findings[0]["title"] if findings else None)
            if len(saved_order) == 1:
                fast_saved.set()

        with mock.patch("scanner.rag.lsast_scanner.run_semgrep",
                        return_value=_parallel_findings()), \
             mock.patch("scanner.rag.lsast_scanner.verify", side_effect=_verify_variable_speed), \
             mock.patch("scanner.rag.lsast_scanner.save_findings_to_db", side_effect=_tracking_save), \
             mock.patch.dict(os.environ, {"LSAST_MAX_WORKERS": "6"}):
            worker = threading.Thread(target=lsast_scan_folder, args=("/x", "s1", "u1"))
            worker.start()
            # The fast finding must be saved well before we release the slow ones.
            self.assertTrue(fast_saved.wait(timeout=5),
                            "first finding was not persisted before the batch finished")
            slow_release.set()
            worker.join(timeout=5)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_lsast_scanner.ParallelIdentityTests.test_finding_persists_before_the_whole_batch_finishes -v 2`
Expected: FAIL — `fast_saved.wait(timeout=5)` times out and returns `False`, since today's code
blocks on `list(ex.map(...))` until the slow (blocked-on-`slow_release`) findings finish too,
which never happens within the 5s test timeout because the test itself controls `slow_release`.

- [ ] **Step 3: Write the implementation**

In `server/scanner/rag/lsast_scanner.py`, replace the whole block from `visible: list[dict] = []`
through the end of the persist `for outcome in outcomes:` loop with:

```python
    visible: list[dict] = []
    filtered: list[dict] = []
    total = len(sem_findings)
    processed = 0

    def _persist(outcome):
        nonlocal processed
        processed += 1
        if outcome is not None:
            if outcome.action == "suppress":
                filtered.append(outcome.finding)
            else:
                visible.append(outcome.finding)
                # A persistence hiccup on one finding must not sink the whole scan.
                try:
                    save_findings_to_db([outcome.finding])
                except Exception as exc:  # noqa: BLE001
                    logger.warning("LSAST: incremental persist failed: %s", exc)
        # Runs for every attempted finding (errored/suppressed/visible alike) so
        # the progress bar reflects real work done, not just visible findings.
        update_progress(scan_id, scanned=processed, total=total, findings=len(visible))

    workers = _max_workers()
    cancelled = False
    if workers > 1 and len(sem_findings) > 1:
        ex = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="lsast")
        try:
            for outcome in ex.map(
                    lambda sf: _process_one(sf, scan_id, triggered_by, llm_ok), sem_findings):
                _persist(outcome)
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    break
        finally:
            # On cancel: don't wait for/run not-yet-started work; already-started
            # calls (bounded by `workers`) finish on their own and their results
            # are simply never persisted, since we've stopped consuming the
            # iterator. On the normal path this is identical to the old `with`
            # block's default wait=True behavior.
            ex.shutdown(wait=not cancelled, cancel_futures=cancelled)
    else:
        for sf in sem_findings:
            _persist(_process_one(sf, scan_id, triggered_by, llm_ok))
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break
```

Delete the old `outcomes = list(ex.map(...))` / `outcomes = [...]` block and the old
`for outcome in outcomes:` persist loop entirely (both are replaced by the code above). Update the
function's closing log line to also report whether it stopped early:

```python
    logger.info(
        "LSAST done%s: %d Semgrep -> %d visible (%d needs_review) + %d filtered",
        " (cancelled)" if cancelled else "",
        len(sem_findings),
        len(visible),
        sum(1 for f in visible if f.get("status") == "needs_review"),
        len(filtered),
    )
    return visible, filtered
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_lsast_scanner -v 2`
Expected: `OK` — including the pre-existing `test_verify_calls_actually_overlap` (Barrier-based) and
`test_parallel_matches_serial` tests, which must still pass unchanged since this refactor doesn't
change the final visible/filtered partition, only when persistence happens.

- [ ] **Step 5: Write the failing test — cancel stops the batch early**

Add to `server/scanner/tests/test_lsast_scanner.py`, inside `class ParallelIdentityTests`:

```python
    def test_cancel_event_stops_remaining_findings(self):
        import threading
        cancel_event = threading.Event()
        started = threading.Event()

        def _verify_and_cancel_after_first(**kw):
            result = _verify_by_excerpt(**kw)
            if kw["code_excerpt"] == "e1":
                cancel_event.set()
            started.set()
            return result

        with mock.patch("scanner.rag.lsast_scanner.run_semgrep",
                        return_value=_parallel_findings()), \
             mock.patch("scanner.rag.lsast_scanner.verify",
                        side_effect=_verify_and_cancel_after_first), \
             mock.patch.dict(os.environ, {"LSAST_MAX_WORKERS": "1"}):  # serial: deterministic order
            visible, filtered = lsast_scan_folder("/x", "s1", "u1", cancel_event=cancel_event)
        # Serial path processes "a" (e1) first, sets cancel_event, then stops
        # before processing b..f.
        self.assertEqual(len(visible) + len(filtered), 1)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_lsast_scanner.ParallelIdentityTests.test_cancel_event_stops_remaining_findings -v 2`
Expected: `OK`

- [ ] **Step 7: Run the full scanner test suite to check for regressions**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner -v 2`
Expected: `OK`, same pass count as before this task plus the new tests (no regressions in
`test_scanner.py`, `test_finding_normalizer.py`, etc.)

- [ ] **Step 8: Commit**

```bash
git add server/scanner/rag/lsast_scanner.py server/scanner/tests/test_lsast_scanner.py
git commit -m "feat(scanner): persist findings as they complete instead of batching to the end

Findings now save (and Scan.files_scanned/total_files progress updates)
within moments of each finding's LLM call finishing, rather than only after
every finding in the batch is done. A cancel_event, when passed, is checked
between findings so cancellation stops promptly instead of running the full
batch to completion."
```

---

### Task 9: `scanner.py` — thread `skip_fingerprints`/`cancel_event` through; fix the AST-failure and cancel statuses

**Files:**
- Modify: `server/scanner/rag/scanner.py`
- Modify: `server/scanner/tests/test_scanner.py`

- [ ] **Step 1: Read the existing test file for fixture conventions**

Read `server/scanner/tests/test_scanner.py` in full before writing new tests, so the new tests
below match its existing mocking style exactly (it already has `ScanFolderTests` covering the
AST-failure and LSAST-failure paths — extend that class, don't create a new one).

- [ ] **Step 2: Write the failing tests**

Add to `server/scanner/tests/test_scanner.py`, inside the existing `ScanFolderTests` class (follow
whatever mock-patching pattern the existing AST-failure test in that file already uses for
`analyze_folder`/`update_progress`):

```python
    @mock.patch("scanner.rag.scanner.lsast_scan_folder")
    @mock.patch("scanner.rag.scanner.analyze_folder", side_effect=RuntimeError("ast boom"))
    @mock.patch("scanner.rag.scanner.update_progress")
    def test_ast_failure_now_marks_interrupted_not_failed(self, mock_progress, _analyze, _lsast):
        from scanner.rag.scanner import scan_folder
        scan_folder(folder_path="/tmp/code", scan_id="s1", triggered_by="u1", scan_name="n")
        # Find the call that set the terminal status.
        status_calls = [c.kwargs.get("status") for c in mock_progress.call_args_list
                        if c.kwargs.get("status")]
        self.assertIn("interrupted", status_calls)
        self.assertNotIn("failed", status_calls)

    @mock.patch("scanner.rag.scanner.lsast_scan_folder")
    @mock.patch("scanner.rag.scanner.analyze_folder",
                return_value={"total_files": 1, "total_functions": 1, "total_loc": 10, "languages": ["python"]})
    @mock.patch("scanner.rag.scanner.update_progress")
    def test_cancelled_run_marks_status_cancelled(self, mock_progress, _analyze, mock_lsast):
        import threading
        from scanner.rag.scanner import scan_folder
        cancel_event = threading.Event()
        cancel_event.set()  # already cancelled by the time lsast_scan_folder returns
        mock_lsast.return_value = ([{"cwe": "CWE-89"}], [])
        scan_folder(folder_path="/tmp/code", scan_id="s1", triggered_by="u1", scan_name="n",
                    cancel_event=cancel_event)
        status_calls = [c.kwargs.get("status") for c in mock_progress.call_args_list
                        if c.kwargs.get("status")]
        self.assertIn("cancelled", status_calls)
        self.assertNotIn("completed", status_calls)

    @mock.patch("scanner.rag.scanner.lsast_scan_folder")
    @mock.patch("scanner.rag.scanner.analyze_folder",
                return_value={"total_files": 1, "total_functions": 1, "total_loc": 10, "languages": ["python"]})
    @mock.patch("scanner.rag.scanner.update_progress")
    def test_skip_fingerprints_passed_through_to_lsast(self, _progress, _analyze, mock_lsast):
        from scanner.rag.scanner import scan_folder
        mock_lsast.return_value = ([], [])
        skip = frozenset({"abc"})
        scan_folder(folder_path="/tmp/code", scan_id="s1", triggered_by="u1", scan_name="n",
                    skip_fingerprints=skip)
        self.assertEqual(mock_lsast.call_args.kwargs["skip_fingerprints"], skip)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_scanner -v 2`
Expected: FAIL — `test_ast_failure_now_marks_interrupted_not_failed` fails because today's code
still passes `status="failed"`; the other two fail with `TypeError: scan_folder() got an
unexpected keyword argument`.

- [ ] **Step 4: Write the implementation**

Replace the full contents of `server/scanner/rag/scanner.py` with:

```python
from .progress import update_progress
from .ast_parser import analyze_folder
from .lsast_scanner import lsast_scan_folder
from datetime import datetime, timezone
import traceback
import logging

logger = logging.getLogger(__name__)


def scan_folder(folder_path, scan_id, triggered_by, scan_name,
                 skip_fingerprints=frozenset(), cancel_event=None):
    """Run a vulnerability scan via the LSAST engine (the only engine).

    LSAST = Semgrep detects -> LLM verifier classifies each finding TP/FP ->
    fusion suppresses false positives and never silently drops a high-severity
    finding. This function owns the scan lifecycle (AST metrics -> in_progress ->
    completed/cancelled/interrupted) and returns the visible (non-suppressed)
    findings.

    ``skip_fingerprints``/``cancel_event`` support resuming an interrupted scan
    -- see scanner/rag/resume.py and local/api_app/views/scan_views.py.
    """
    # ----------------------------------------------------------
    # STEP 1 — AST ANALYSIS (LOC / functions / languages for the dashboard)
    # ----------------------------------------------------------
    try:
        ast_metrics = analyze_folder(folder_path)
        total_files = ast_metrics.get("total_files", 0)
        update_progress(scan_id=scan_id, metrics=ast_metrics, total=total_files)
        logger.info(
            "AST Completed -> LOC: %s | Functions: %s | Languages: %s",
            ast_metrics.get("total_loc"),
            ast_metrics.get("total_functions"),
            ast_metrics.get("languages"),
        )
    except Exception as e:
        logger.error("AST Analysis failed: %s\n%s", e, traceback.format_exc())
        # The extracted source is retained (see scan_views.py) regardless of
        # this failure, so resuming is always safe -- worst case it just
        # retries AST analysis, no worse than a fresh scan. "failed" is
        # reserved for pre-extraction failures where there's nothing to resume.
        update_progress(
            scan_id=scan_id,
            error=str(e),
            status="interrupted",
            end_time=datetime.now(timezone.utc),
        )
        return []

    # ----------------------------------------------------------
    # STEP 2 — LSAST DETECTION + VERIFICATION
    # ----------------------------------------------------------
    update_progress(scan_id=scan_id, status="in_progress")
    visible, _filtered = lsast_scan_folder(
        folder_path, scan_id, triggered_by,
        skip_fingerprints=skip_fingerprints, cancel_event=cancel_event,
    )

    # ----------------------------------------------------------
    # STEP 3 — SCAN COMPLETE (or cancelled mid-way)
    # ----------------------------------------------------------
    if cancel_event is not None and cancel_event.is_set():
        update_progress(
            scan_id=scan_id,
            findings=len(visible),
            scanned=total_files,
            status="cancelled",
            end_time=datetime.now(timezone.utc),
        )
        logger.info("LSAST scan cancelled: %d findings persisted before stop for %s",
                    len(visible), scan_name or "Unknown")
        return visible

    update_progress(
        scan_id=scan_id,
        findings=len(visible),
        scanned=total_files,   # no per-file progress; on completion all files are done
        status="completed",
        end_time=datetime.now(timezone.utc),
    )
    # Consume a trial slot only on successful completion (no-op when trial mode is
    # off). Failures/cancellation return before reaching here, so they never count.
    try:
        from licenses.services import trial
        trial.record_completion()
    except Exception as exc:  # noqa: BLE001 — trial accounting must never sink a scan
        logger.warning("trial.record_completion failed: %s", exc)
    logger.info("LSAST scan completed: %d findings for %s", len(visible), scan_name or "Unknown")
    return visible
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner.tests.test_scanner -v 2`
Expected: `OK` — including the pre-existing `test_records_error_and_returns_empty_on_ast_failure`
test; if that test asserted the old `status="failed"` value specifically, update its assertion to
`"interrupted"` to match the new (intended) behavior — check its exact assertion when you read the
file in Step 1 and adjust it there rather than leaving two tests contradicting each other.

- [ ] **Step 6: Commit**

```bash
git add server/scanner/rag/scanner.py server/scanner/tests/test_scanner.py
git commit -m "feat(scanner): route skip_fingerprints/cancel_event through scan_folder

AST-analysis failures and mid-scan cancellation now land in 'interrupted'/
'cancelled' instead of 'failed', since the extracted source is retained in
both cases and resuming is always safe."
```

---

### Task 10: `trial.py` — count `interrupted` scans against the trial cap, not `cancelled`

Per spec §7: a pending-resume ("interrupted") scan is genuinely unfinished business and must keep
occupying its trial slot exactly like `queued`/`in_progress` already do; a `cancelled` scan must
not, matching how `failed` already doesn't.

**Files:**
- Modify: `server/licenses/services/trial.py`
- Modify: `server/local/api_app/tests/test_trial.py`

- [ ] **Step 1: Write the failing tests**

Add to `server/local/api_app/tests/test_trial.py`, inside `class TrialGateTests`:

```python
    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_interrupted_scans_count_against_limit(self):
        trial.record_completion()                   # used=1
        _mk_scan("interrupted")                      # +1 pending-resume -> used+ip = 2
        self.assertFalse(trial.can_start())          # blocked even though used (1) < limit (2)

    @mock.patch.dict(os.environ, {"TRIAL_MODE": "true", "TRIAL_SCAN_LIMIT": "2"})
    def test_cancelled_scans_do_not_count_against_limit(self):
        _mk_scan("cancelled")
        self.assertEqual(trial.in_progress(), 0)
        self.assertTrue(trial.can_start())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd server && .venv/Scripts/python.exe manage.py test local.api_app.tests.test_trial -v 2`
Expected: `test_interrupted_scans_count_against_limit` FAILS (`can_start()` returns `True` when it
should be `False`, since `"interrupted"` isn't in `_ACTIVE_STATUSES` yet);
`test_cancelled_scans_do_not_count_against_limit` already passes today (nothing needs to change for
it) — that's fine, it's here as a permanent regression guard against `cancelled` ever being added
to `_ACTIVE_STATUSES` by mistake later.

- [ ] **Step 3: Write the implementation**

In `server/licenses/services/trial.py`, change:

```python
_ACTIVE_STATUSES = ("queued", "in_progress")
```

to:

```python
_ACTIVE_STATUSES = ("queued", "in_progress", "interrupted")
```

And update the module docstring's counting-policy paragraph (lines 12-16) to mention it:

```python
Counting policy: a slot is consumed only on SUCCESSFUL completion
(``record_completion`` is called from each pipeline's completion step, which
failed scans never reach). In-progress/queued/interrupted scans of EITHER type
are counted against the limit at creation time (and while pending resume) so
concurrent submissions can't overshoot the cap. A user-cancelled scan does
NOT count -- same as a failed one, no slot was ever completed.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd server && .venv/Scripts/python.exe manage.py test local.api_app.tests.test_trial -v 2`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add server/licenses/services/trial.py server/local/api_app/tests/test_trial.py
git commit -m "feat(trial): count interrupted (pending-resume) scans against the cap

Cancelled scans deliberately do not count, matching failed -- only
interrupted, queued, and in_progress represent genuinely unfinished work."
```

---

### Task 11: `scan_views.py` — durable source retention + shared pipeline helper

Replaces `tempfile.mkdtemp()` with a durable per-scan directory and removes the always-delete
`finally` blocks from the two LSAST-triggering views, replacing their duplicated thread bodies
with one shared helper both this task and Tasks 11-12 build on.

**Files:**
- Modify: `server/local/api_app/views/scan_views.py`
- Modify: `server/local/api_app/tests/test_scan_views.py`

- [ ] **Step 1: Write the failing test**

Add to `server/local/api_app/tests/test_scan_views.py` (new test class, after the existing ones):

```python
class SourceRetentionTests(TestCase):
    """The extracted source must survive a scan (success or failure) instead of
    being deleted unconditionally -- that's the whole precondition for resume."""

    def test_source_path_recorded_and_retained_after_zip_scan(self):
        good_zip = SimpleUploadedFile("good.zip", _valid_zip_bytes(), content_type="application/zip")
        request = _multipart_request("/api/scans/create/", {
            "scan_name": "retained-code", "project_id": "p1", "zip_file": good_zip,
        })
        with mock.patch("local.api_app.views.scan_views.scan_folder", return_value=[]):
            response = ScanCreateView.post.__wrapped__(ScanCreateView(), request)
        self.assertEqual(response.status_code, 202)
        scan = Scan.objects.get(scan_name="retained-code")
        self.assertTrue(scan.source_path)
        self.assertTrue(os.path.isdir(scan.source_path))
        self.assertTrue(os.path.isfile(os.path.join(scan.source_path, "file.txt")))
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && .venv/Scripts/python.exe manage.py test local.api_app.tests.test_scan_views.SourceRetentionTests -v 2`
Expected: FAIL — `scan.source_path` is empty (field not populated yet).

- [ ] **Step 3: Write the implementation**

In `server/local/api_app/views/scan_views.py`:

Add these imports near the top (with the other `scanner.rag`/`local.api_app` imports):

```python
from scanner.rag.resume import already_done_fingerprints
```

Add a module-level cancel-event registry near the existing `scan_thread`/`scan_thread_lock`
globals:

```python
scan_thread = None
scan_thread_lock = threading.Lock()
# Cooperative-cancel signals for the scan currently running, keyed by scan_id.
# Only ever has at most one live entry given the one-scan-at-a-time invariant
# above, but keyed defensively rather than assuming that never changes.
_cancel_events: dict[str, threading.Event] = {}
```

Add a shared pipeline-runner helper (place it right after the globals, before `ScanCreateView`):

```python
def _run_lsast_pipeline(scan_id, source_path, triggered_by, scan_name,
                        skip_fingerprints=frozenset(), cancel_event=None):
    """Runs the LSAST pipeline over an already-extracted source_path and updates
    the Scan row accordingly. Shared by a fresh scan and a resumed one -- the
    only difference between the two call sites is what skip_fingerprints/
    cancel_event they pass in.

    Once source_path exists, any non-'completed'/'cancelled' outcome lands in
    'interrupted' (never 'failed') -- resuming is always safe from here since
    the source is retained regardless of how this call ends.
    """
    try:
        findings = scan_folder(
            folder_path=source_path,
            scan_id=scan_id,
            triggered_by=triggered_by,
            scan_name=scan_name,
            skip_fingerprints=skip_fingerprints,
            cancel_event=cancel_event,
        )
        logging.info(f"Scan run finished. Found {len(findings) if findings else 0} vulnerabilities.")
    except Exception as e:
        logging.error(f"Error during scan: {e}")
        ScanModel.update_status(scan_id, "interrupted")
        update_progress(
            scan_id=scan_id,
            status="interrupted",
            end_time=datetime.now(timezone.utc),
            error=str(e),
        )
        import traceback
        logging.error(traceback.format_exc())
    finally:
        _cancel_events.pop(scan_id, None)
        # This thread never goes through Django's request_started/
        # request_finished signals, so its DB connection is never
        # auto-closed -- release it explicitly.
        close_old_connections()
```

Now change `ScanCreateView.post`. Replace the temp-dir setup:

```python
            # Create temporary directory for both ZIP file and extraction
            temp_dir = tempfile.mkdtemp()
            temp_zip_path = os.path.join(temp_dir, zip_file.name)
            extracted_folder_path = os.path.join(temp_dir, 'extracted')
```

with a durable, per-scan directory:

```python
            # Extracted source is retained (not a throwaway temp dir) so an
            # interrupted/cancelled scan can be resumed without re-uploading.
            scan_dir = os.path.join(MEDIA_ROOT, str(scan_id))
            temp_dir = os.path.join(scan_dir, "upload")
            extracted_folder_path = os.path.join(scan_dir, "source")
            os.makedirs(temp_dir, exist_ok=True)
            temp_zip_path = os.path.join(temp_dir, zip_file.name)
            Scan.objects.filter(id=scan_id).update(source_path=extracted_folder_path)
```

Add the `Scan` import at the top of the file (alongside the existing `SbomModel`/`ScanModel`
imports):

```python
from local.api_app.models.orm import Scan
```

The `BadZipFile`/generic `Exception` handlers right after extraction stay exactly as they are
(`ScanModel.update_status(scan_id, "failed")` + `shutil.rmtree(temp_dir)`) — nothing extracted
successfully yet at that point, so there's genuinely nothing to resume; only clean up the `upload`
subdir there, not the whole `scan_dir` (leave `source_path` blank since it was never set to a
successful value):

```python
            except zipfile.BadZipFile:
                logging.error("Uploaded file is not a valid ZIP file")
                ScanModel.update_status(scan_id, "failed")
                shutil.rmtree(scan_dir, ignore_errors=True)
                return JsonResponse({"error": "Invalid zip file"}, status=status.HTTP_400_BAD_REQUEST)

            except Exception as e:
                logging.error(f"Failed to process uploaded file: {e}")
                ScanModel.update_status(scan_id, "failed")
                shutil.rmtree(scan_dir, ignore_errors=True)
                return JsonResponse({"detail": "Failed to process uploaded file."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

Replace the whole `run_scan()` closure and its dispatch with a call to the shared helper. Delete
the `def run_scan(): ...` function entirely and replace the dispatch block:

```python
            global scan_thread
            with scan_thread_lock:
                if scan_thread and scan_thread.is_alive():
                    ScanModel.update_status(scan_id, "failed")
                    shutil.rmtree(scan_dir, ignore_errors=True)
                    return JsonResponse({"detail": "Scan already in progress."}, status=status.HTTP_409_CONFLICT)
                cancel_event = threading.Event()
                _cancel_events[scan_id] = cancel_event
                scan_thread = threading.Thread(
                    target=_run_lsast_pipeline,
                    args=(scan_id, extracted_folder_path, triggered_by, scan_name),
                    kwargs={"cancel_event": cancel_event},
                    daemon=True,
                )
                scan_thread.start()
```

(Note: the extraction has already succeeded by the time this block runs, so `source_path` is
already durable on the row — the thread-conflict branch above intentionally still wipes `scan_dir`
since that particular row is being marked `"failed"`, not `"interrupted"`, matching existing
behavior for the concurrency-conflict case.)

Now apply the identical treatment to `GitHubRepoScanView.post`. Its `run_github_scan()` downloads
into a folder returned by `scan_github_repo(...)` rather than extracting a zip — record that path
as `source_path` right after the clone succeeds, and dispatch through `_run_lsast_pipeline` the
same way:

```python
        # Background thread
        def run_github_scan():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                result = loop.run_until_complete(
                    scan_github_repo(token, username, repo, branch)
                )
                folder_path = result["folder_path"]
                Scan.objects.filter(id=scan_id).update(source_path=folder_path)

                cancel_event = _cancel_events.get(scan_id)
                findings = scan_folder(
                    folder_path=folder_path,
                    scan_id=scan_id,
                    triggered_by=triggered_by,
                    scan_name=scan_name,
                    cancel_event=cancel_event,
                )

            except Exception as e:
                logging.error(f"GitHub scan failed: {e}")
                ScanModel.update_status(scan_id, "interrupted")
                update_progress(
                    scan_id=scan_id,
                    status="interrupted",
                    end_time=datetime.now(timezone.utc),
                    error=str(e),
                )

            finally:
                _cancel_events.pop(scan_id, None)
                close_old_connections()

        global scan_thread
        with scan_thread_lock:
            if scan_thread and scan_thread.is_alive():
                ScanModel.update_status(scan_id, "failed")
                return Response(
                    {"detail": "Another scan already in progress."},
                    status=status.HTTP_409_CONFLICT,
                )
            _cancel_events[scan_id] = threading.Event()
            scan_thread = threading.Thread(target=run_github_scan, daemon=True)
            scan_thread.start()
```

(`GitHubRepoScanView` keeps its own inline closure rather than `_run_lsast_pipeline` because its
source isn't known until *after* the clone step inside the thread — `_run_lsast_pipeline` assumes
`source_path` is already set before the thread starts, which holds for the zip/resume cases but
not this one. This is intentionally not force-unified; the shared helper covers the two cases
where it's a clean fit.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test local.api_app.tests.test_scan_views -v 2`
Expected: `OK` — including all the pre-existing `ScanCreationOrphanedRowTests`/
`TrialSlotNotConsumedOnFailureTests` tests (bad-zip and thread-conflict paths still end in
`"failed"`, unchanged).

- [ ] **Step 5: Run the full backend suite to check for regressions**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner local.api_app -v 2`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add server/local/api_app/views/scan_views.py server/local/api_app/tests/test_scan_views.py
git commit -m "feat(scan): retain extracted source in a durable path instead of deleting it

Both ScanCreateView and GitHubRepoScanView now record Scan.source_path and
keep the extracted folder around instead of unconditionally rmtree-ing it,
which is the precondition for resuming a scan. Failures that happen after
extraction now land in 'interrupted' via a shared _run_lsast_pipeline()
helper instead of 'failed' -- see Task 9's scanner.py change for why."
```

---

### Task 12: `scan_views.py` — `ScanCancelView`

**Files:**
- Modify: `server/local/api_app/views/scan_views.py`
- Modify: `server/local/api_app/urls/scan_urls.py`
- Modify: `server/local/api_app/tests/test_scan_views.py`

- [ ] **Step 1: Write the failing test**

Add to `server/local/api_app/tests/test_scan_views.py`:

```python
class ScanCancelViewTests(TestCase):
    def _make_scan(self, status="in_progress"):
        from datetime import datetime, timezone
        return Scan.objects.create(
            project_id="p1", scan_name="cancel-me", status=status,
            created_at=datetime.now(timezone.utc), deleted=False,
        )

    def _cancel_request(self, scan_id):
        factory = APIRequestFactory()
        django_request = factory.post(f"/api/scans/{scan_id}/cancel/")
        request = Request(django_request, parsers=[JSONParser()])
        request.user = {"id": "tester"}
        return request

    def test_sets_cancel_requested_and_returns_202(self):
        from local.api_app.views.scan_views import ScanCancelView
        scan = self._make_scan()
        request = self._cancel_request(scan.id)
        response = ScanCancelView.post.__wrapped__(ScanCancelView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 202)
        scan.refresh_from_db()
        self.assertTrue(scan.cancel_requested)

    def test_sets_the_in_memory_event_for_the_running_scan(self):
        from local.api_app.views import scan_views
        from local.api_app.views.scan_views import ScanCancelView
        scan = self._make_scan()
        event = threading.Event()
        scan_views._cancel_events[scan.id] = event
        self.addCleanup(scan_views._cancel_events.pop, scan.id, None)
        request = self._cancel_request(scan.id)
        ScanCancelView.post.__wrapped__(ScanCancelView(), request, scan_id=scan.id)
        self.assertTrue(event.is_set())

    def test_404_for_unknown_scan(self):
        from local.api_app.views.scan_views import ScanCancelView
        request = self._cancel_request("no-such-id")
        response = ScanCancelView.post.__wrapped__(ScanCancelView(), request, scan_id="no-such-id")
        self.assertEqual(response.status_code, 404)

    def test_409_for_already_terminal_scan(self):
        from local.api_app.views.scan_views import ScanCancelView
        scan = self._make_scan(status="completed")
        request = self._cancel_request(scan.id)
        response = ScanCancelView.post.__wrapped__(ScanCancelView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 409)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && .venv/Scripts/python.exe manage.py test local.api_app.tests.test_scan_views.ScanCancelViewTests -v 2`
Expected: FAIL with `ImportError: cannot import name 'ScanCancelView'`

- [ ] **Step 3: Write the implementation**

Add to `server/local/api_app/views/scan_views.py`, after `GitHubRepoScanView`:

```python
class ScanCancelView(APIView):
    @require_permission("delete_scan")
    def post(self, request, scan_id):
        scan = ScanModel.find_by_id(scan_id=scan_id)
        if not scan:
            return JsonResponse({"error": "Scan not found"}, status=status.HTTP_404_NOT_FOUND)
        if scan["status"] not in ("queued", "in_progress"):
            return JsonResponse(
                {"detail": f"Scan is {scan['status']}, nothing to cancel."},
                status=status.HTTP_409_CONFLICT,
            )
        Scan.objects.filter(id=scan_id).update(cancel_requested=True)
        event = _cancel_events.get(scan_id)
        if event is not None:
            event.set()
        return JsonResponse({"detail": "Cancellation requested."}, status=status.HTTP_202_ACCEPTED)
```

- [ ] **Step 4: Wire the URL**

In `server/local/api_app/urls/scan_urls.py`, add the import and route:

```python
from ..views.scan_views import (
    ScanCreateView, ScanDetailView, ScanListView, GitHubRepoScanView,
    SbomCreateView, SbomScanDetailView, GrypeCreateView, ScanCancelView,
)
```

```python
    path("<str:scan_id>/cancel/", ScanCancelView.as_view(), name="scan-cancel"),
```

(add it next to the existing `path("<str:scan_id>/", ScanDetailView.as_view(), ...)` line)

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test local.api_app.tests.test_scan_views.ScanCancelViewTests -v 2`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add server/local/api_app/views/scan_views.py server/local/api_app/urls/scan_urls.py server/local/api_app/tests/test_scan_views.py
git commit -m "feat(scan): add ScanCancelView for explicit user-initiated cancellation"
```

---

### Task 13: `scan_views.py` — `ScanResumeView`

**Files:**
- Modify: `server/local/api_app/views/scan_views.py`
- Modify: `server/local/api_app/urls/scan_urls.py`
- Modify: `server/local/api_app/tests/test_scan_views.py`

- [ ] **Step 1: Write the failing test**

Add to `server/local/api_app/tests/test_scan_views.py`:

```python
class ScanResumeViewTests(TestCase):
    def _make_scan(self, status="interrupted", source_path=None, cancel_requested=False):
        from datetime import datetime, timezone
        return Scan.objects.create(
            project_id="p1", scan_name="resume-me", status=status,
            created_at=datetime.now(timezone.utc), deleted=False,
            source_path=source_path or "", cancel_requested=cancel_requested,
        )

    def _resume_request(self, scan_id):
        factory = APIRequestFactory()
        django_request = factory.post(f"/api/scans/{scan_id}/resume/")
        request = Request(django_request, parsers=[JSONParser()])
        request.user = {"id": "tester"}
        return request

    def test_404_for_unknown_scan(self):
        from local.api_app.views.scan_views import ScanResumeView
        request = self._resume_request("no-such-id")
        response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id="no-such-id")
        self.assertEqual(response.status_code, 404)

    def test_409_for_a_non_resumable_status(self):
        from local.api_app.views.scan_views import ScanResumeView
        scan = self._make_scan(status="completed", source_path="/tmp/whatever")
        request = self._resume_request(scan.id)
        response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 409)

    def test_410_when_source_path_missing_on_disk(self):
        from local.api_app.views.scan_views import ScanResumeView
        scan = self._make_scan(source_path="/tmp/does-not-exist-at-all-xyz")
        request = self._resume_request(scan.id)
        response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 410)
        scan.refresh_from_db()
        self.assertEqual(scan.status, "failed")

    def test_starts_the_pipeline_and_clears_cancel_requested(self):
        import tempfile
        from local.api_app.views.scan_views import ScanResumeView
        source_dir = tempfile.mkdtemp()
        scan = self._make_scan(source_path=source_dir, cancel_requested=True)
        request = self._resume_request(scan.id)
        with mock.patch("local.api_app.views.scan_views.scan_folder", return_value=[]):
            response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 202)
        scan.refresh_from_db()
        self.assertFalse(scan.cancel_requested)

    def test_conflicts_with_an_already_running_scan(self):
        from local.api_app.views import scan_views
        from local.api_app.views.scan_views import ScanResumeView
        scan = self._make_scan(source_path="/tmp/whatever-exists-or-not")
        stop_event = threading.Event()
        t = threading.Thread(target=stop_event.wait, daemon=True)
        t.start()
        scan_views.scan_thread = t
        def _cleanup():
            stop_event.set(); t.join(timeout=1); scan_views.scan_thread = None
        self.addCleanup(_cleanup)
        os.makedirs(scan.source_path, exist_ok=True)
        self.addCleanup(lambda: __import__("shutil").rmtree(scan.source_path, ignore_errors=True))
        request = self._resume_request(scan.id)
        response = ScanResumeView.post.__wrapped__(ScanResumeView(), request, scan_id=scan.id)
        self.assertEqual(response.status_code, 409)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && .venv/Scripts/python.exe manage.py test local.api_app.tests.test_scan_views.ScanResumeViewTests -v 2`
Expected: FAIL with `ImportError: cannot import name 'ScanResumeView'`

- [ ] **Step 3: Write the implementation**

Add to `server/local/api_app/views/scan_views.py`, after `ScanCancelView`:

```python
class ScanResumeView(APIView):
    @require_permission("create_scan")
    def post(self, request, scan_id):
        scan = ScanModel.find_by_id(scan_id=scan_id)
        if not scan:
            return JsonResponse({"error": "Scan not found"}, status=status.HTTP_404_NOT_FOUND)
        if scan["status"] not in ("interrupted", "cancelled"):
            return JsonResponse(
                {"detail": f"Scan is {scan['status']}, not resumable."},
                status=status.HTTP_409_CONFLICT,
            )

        source_path = Scan.objects.filter(id=scan_id).values_list("source_path", flat=True).first()
        if not source_path or not os.path.isdir(source_path):
            ScanModel.update_status(scan_id, "failed")
            return JsonResponse(
                {"detail": "Source is no longer available; please start a new scan."},
                status=status.HTTP_410_GONE,
            )

        global scan_thread
        with scan_thread_lock:
            if scan_thread and scan_thread.is_alive():
                return JsonResponse(
                    {"detail": "Another scan already in progress."},
                    status=status.HTTP_409_CONFLICT,
                )
            Scan.objects.filter(id=scan_id).update(cancel_requested=False, status="in_progress")
            cancel_event = threading.Event()
            _cancel_events[scan_id] = cancel_event
            skip = already_done_fingerprints(scan_id)
            scan_thread = threading.Thread(
                target=_run_lsast_pipeline,
                args=(scan_id, source_path, scan["triggered_by"], scan["scan_name"]),
                kwargs={"skip_fingerprints": skip, "cancel_event": cancel_event},
                daemon=True,
            )
            scan_thread.start()

        return JsonResponse({"detail": "Scan resumed.", "scan": scan}, status=status.HTTP_202_ACCEPTED)
```

- [ ] **Step 4: Wire the URL**

In `server/local/api_app/urls/scan_urls.py`, add `ScanResumeView` to the import list from Task 12
and add:

```python
    path("<str:scan_id>/resume/", ScanResumeView.as_view(), name="scan-resume"),
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd server && .venv/Scripts/python.exe manage.py test local.api_app.tests.test_scan_views.ScanResumeViewTests -v 2`
Expected: `OK`

- [ ] **Step 6: Run the full backend suite**

Run: `cd server && .venv/Scripts/python.exe manage.py test scanner local.api_app -v 2`
Expected: `OK`, no regressions.

- [ ] **Step 7: Commit**

```bash
git add server/local/api_app/views/scan_views.py server/local/api_app/urls/scan_urls.py server/local/api_app/tests/test_scan_views.py
git commit -m "feat(scan): add ScanResumeView -- manual resume for interrupted/cancelled scans

Resumes reuse the retained source_path and skip any finding already
persisted (via already_done_fingerprints), so only genuinely new work goes
through the LLM verify/enrich step."
```

---

### Task 14: `run_server.py` — startup reconciliation

**Files:**
- Modify: `server/run_server.py`

There's no existing test harness for `run_server.py` (it's a thin process entrypoint, not imported
by the Django test suite) — verify this one manually per Step 2 below, consistent with how other
entrypoint-level changes in this project are checked (e.g. `build_windows.ps1`'s syntax-check
convention noted in `CLAUDE.md`).

- [ ] **Step 1: Add the reconciliation call**

In `server/run_server.py`, add the call right after the `migrate` command and before
`collectstatic`:

```python
    from django.core.management import call_command
    call_command("migrate", interactive=False, verbosity=0)

    from scanner.rag.resume import reconcile_orphaned_scans
    reconciled = reconcile_orphaned_scans()
    if reconciled:
        print(f"Reconciled {reconciled} orphaned scan(s) from a previous run", flush=True)

    # Gather admin/DRF assets so they render with DEBUG off (no-op if already present).
    call_command("collectstatic", interactive=False, verbosity=0)
```

- [ ] **Step 2: Verify manually**

Run: `cd server && .venv/Scripts/python.exe -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codesense.settings'); django.setup(); from scanner.rag.resume import reconcile_orphaned_scans; print(reconcile_orphaned_scans())"`
Expected: prints `0` (or a small integer) with no traceback — confirms the import and DB query
work against the real settings module, not just inside a test's isolated DB.

- [ ] **Step 3: Commit**

```bash
git add server/run_server.py
git commit -m "feat(scan): reconcile crash-orphaned scans at real server startup

Wired into run_server.py (the actual codesense-server entrypoint) rather
than Django's AppConfig.ready(), which also fires for manage.py test and
arbitrary management commands -- this runs exactly once per real process
launch."
```

---

### Task 15: Full regression pass

**Files:** none (verification only)

- [ ] **Step 1: Run the complete backend suite**

Run: `cd server && .venv/Scripts/python.exe manage.py test`
Expected: `OK`, with the same 5 pre-existing skips noted throughout this session (characterization
tests needing `SEMGREP_BIN`/`SEMGREP_RULES_DIR`), plus every test added across Tasks 1-13 passing.
Total test count should be at least 228 (the count at the start of this feature) + the ~35 new
tests added across this plan.

- [ ] **Step 2: If anything fails, fix forward**

Do not skip or comment out a failing test to get to green — every regression here means a real
behavior this plan changed broke something not accounted for above. Fix the root cause and re-run.

- [ ] **Step 3: Final commit (only if Step 2 required fixes)**

```bash
git add -A
git commit -m "fix(scan): address regressions found in full-suite verification pass"
```

(Skip this commit entirely if Step 1 was already green — don't create an empty commit.)

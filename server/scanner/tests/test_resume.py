from datetime import datetime, timezone

from django.test import SimpleTestCase, TestCase

from local.api_app.models.orm import Finding
from scanner.rag.lsast_types import SemgrepFinding
from scanner.rag.resume import fingerprint, already_done_fingerprints


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

    def test_delimiter_in_fields_does_not_cause_false_collision(self):
        # A naive ":".join would make these two different findings hash the
        # same: "dir:1" + ":" + "2" + ":" + "rule" == "dir" + ":" + "1" + ":" + "2:rule"
        a = fingerprint(_finding(file_path="dir:1", start_line=2, rule_id="rule"))
        b = fingerprint(_finding(file_path="dir", start_line=1, rule_id="2:rule"))
        self.assertNotEqual(a, b)


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

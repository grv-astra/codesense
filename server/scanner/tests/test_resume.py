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

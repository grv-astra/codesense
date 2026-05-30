import os
from unittest import mock

from django.test import SimpleTestCase

from scanner.services.tools import get_semgrep_bin, get_semgrep_rules_dir


class BundleEnvVarSmokeTests(SimpleTestCase):
    def test_semgrep_env_wiring_is_picked_up(self):
        with mock.patch.dict(os.environ,
                             {"SEMGREP_BIN": "/fake/sem", "SEMGREP_RULES_DIR": "/fake/rules"},
                             clear=False):
            self.assertEqual(get_semgrep_bin(), "/fake/sem")
            self.assertEqual(get_semgrep_rules_dir(), "/fake/rules")

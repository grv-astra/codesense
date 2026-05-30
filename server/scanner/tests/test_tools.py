import os
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from scanner.services import tools
from scanner.services.tools import get_semgrep_bin, get_semgrep_rules_dir


class ToolPathTests(SimpleTestCase):
    def tearDown(self):
        for k in ("GRYPE_BIN", "SYFT_BIN", "SCANNER_TOOLS_DIR",
                  "GRYPE_DB_CACHE_DIR", "COSIGN_KEY_DIR"):
            os.environ.pop(k, None)

    def test_env_override_wins(self):
        os.environ["GRYPE_BIN"] = "/bundle/grype.exe"
        self.assertEqual(tools.tool_path("grype"), "/bundle/grype.exe")

    def test_falls_back_to_bare_name(self):
        self.assertEqual(tools.tool_path("syft"), "syft")

    def test_grype_offline_env_pins_db(self):
        os.environ["GRYPE_DB_CACHE_DIR"] = "/bundle/grype-db"
        env = tools.grype_offline_env()
        self.assertEqual(env["GRYPE_DB_CACHE_DIR"], "/bundle/grype-db")
        self.assertEqual(env["GRYPE_DB_AUTO_UPDATE"], "false")
        self.assertEqual(env["GRYPE_DB_VALIDATE_AGE"], "false")

    def test_grype_offline_env_noop_without_db(self):
        env = tools.grype_offline_env()
        self.assertNotIn("GRYPE_DB_AUTO_UPDATE", env)

    def test_cosign_paths_use_key_dir_override(self):
        os.environ["COSIGN_KEY_DIR"] = "/data/keys"
        priv, pub, cfg = tools.cosign_paths()
        self.assertEqual(priv, "/data/keys/cosign.key")
        self.assertEqual(pub, "/data/keys/cosign.pub")
        self.assertEqual(cfg, "/data/keys/signing-config.json")


class SemgrepResolverTests(SimpleTestCase):
    def test_semgrep_bin_uses_env_var_when_set(self):
        with mock.patch.dict(os.environ, {"SEMGREP_BIN": "/custom/path/semgrep"}, clear=False):
            self.assertEqual(get_semgrep_bin(), "/custom/path/semgrep")

    def test_semgrep_bin_falls_back_to_tools_dir(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "semgrep").write_text("#!/bin/sh\n")
            os.chmod(Path(d) / "semgrep", 0o755)
            with mock.patch.dict(os.environ,
                                 {"SCANNER_TOOLS_DIR": d, "SEMGREP_BIN": ""},
                                 clear=False):
                self.assertEqual(get_semgrep_bin(), str(Path(d) / "semgrep"))

    def test_semgrep_bin_falls_back_to_path_name(self):
        with mock.patch.dict(os.environ,
                             {"SEMGREP_BIN": "", "SCANNER_TOOLS_DIR": ""},
                             clear=False):
            self.assertEqual(get_semgrep_bin(), "semgrep")

    def test_semgrep_rules_dir_uses_env_var(self):
        with mock.patch.dict(os.environ, {"SEMGREP_RULES_DIR": "/opt/rules"}, clear=False):
            self.assertEqual(get_semgrep_rules_dir(), "/opt/rules")

    def test_semgrep_rules_dir_returns_empty_when_unset(self):
        with mock.patch.dict(os.environ, {"SEMGREP_RULES_DIR": ""}, clear=False):
            self.assertEqual(get_semgrep_rules_dir(), "")

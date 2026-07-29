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
        # Use a platform-rooted key dir so the expectation holds on POSIX and
        # Windows alike (production resolves the path with pathlib).
        key_dir = os.path.join(os.sep, "data", "keys")
        os.environ["COSIGN_KEY_DIR"] = key_dir
        priv, pub, cfg = tools.cosign_paths()
        base = Path(key_dir)
        self.assertEqual(priv, str((base / "cosign.key").resolve()))
        self.assertEqual(pub, str((base / "cosign.pub").resolve()))
        self.assertEqual(cfg, str((base / "signing-config.json").resolve()))


class EnsureCosignKeysTests(SimpleTestCase):
    """Covers the fresh-install gap found on the first real client-PC delivery
    (2026-07-20): SBOM signing needs a keypair that init_sbom_signing (manual-
    only) is the sole generator of -- a genuinely fresh machine never has one."""

    def tearDown(self):
        os.environ.pop("COSIGN_KEY_DIR", None)

    def test_generates_keys_and_config_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            key_dir = Path(d) / "keys"
            with mock.patch.dict(
                os.environ,
                {"COSIGN_KEY_DIR": str(key_dir), "COSIGN_PASSWORD": "test-pass-123"},
                clear=False,
            ):
                self.assertFalse(key_dir.exists())
                tools.ensure_cosign_keys()
                priv, pub, cfg = tools.cosign_paths()
                self.assertTrue(Path(priv).exists())
                self.assertTrue(Path(pub).exists())
                self.assertTrue(Path(cfg).exists())

    def test_noop_when_keys_already_exist(self):
        with tempfile.TemporaryDirectory() as d:
            key_dir = Path(d) / "keys"
            with mock.patch.dict(
                os.environ,
                {"COSIGN_KEY_DIR": str(key_dir), "COSIGN_PASSWORD": "test-pass-123"},
                clear=False,
            ):
                tools.ensure_cosign_keys()
                priv, pub, _cfg = tools.cosign_paths()
                first_priv_bytes = Path(priv).read_bytes()
                first_pub_bytes = Path(pub).read_bytes()

                tools.ensure_cosign_keys()  # second call must not regenerate

                self.assertEqual(Path(priv).read_bytes(), first_priv_bytes)
                self.assertEqual(Path(pub).read_bytes(), first_pub_bytes)


class SemgrepResolverTests(SimpleTestCase):
    def test_semgrep_bin_uses_env_var_when_set(self):
        with mock.patch.dict(os.environ, {"SEMGREP_BIN": "/custom/path/semgrep"}, clear=False):
            self.assertEqual(get_semgrep_bin(), "/custom/path/semgrep")

    def test_semgrep_bin_falls_back_to_tools_dir(self):
        with tempfile.TemporaryDirectory() as d:
            # tool_path() looks for "<name>.exe" on Windows, bare name elsewhere.
            exe = "semgrep" + (".exe" if os.name == "nt" else "")
            (Path(d) / exe).write_text("#!/bin/sh\n")
            os.chmod(Path(d) / exe, 0o755)
            with mock.patch.dict(os.environ,
                                 {"SCANNER_TOOLS_DIR": d, "SEMGREP_BIN": ""},
                                 clear=False):
                self.assertEqual(get_semgrep_bin(), str(Path(d) / exe))

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

import os

from django.test import SimpleTestCase

from scanner.services import tools


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

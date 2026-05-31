"""Regression guard for the offline Semgrep rule-bundling defect.

Background: the desktop build clones github.com/semgrep/semgrep-rules and the
launcher points ``SEMGREP_RULES_DIR`` (hence ``semgrep --config``) at that tree's
root. The repo root contains non-rule YAML (``.pre-commit-config.yaml``, CI
workflows, ``*.test.yaml`` fixtures, ...). Semgrep aborts the *entire* run with
rc=7 ("invalid configuration file found") the moment ``--config`` loads any YAML
without a top-level ``rules:`` key, so a packaged scan silently finds nothing.

These tests pin the staging contract: after staging, every ``*.yml``/``*.yaml``
under the bundled rules dir is a loadable Semgrep rule file, making the dir a
valid ``--config`` target.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# The helper is build tooling under scripts/offline_sbom/, imported by path so
# the test runs under pytest, `unittest discover`, or direct execution alike.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stage_semgrep_rules as sgr  # noqa: E402


VALID_RULE = (
    "rules:\n"
    "  - id: eqeq-is-bad\n"
    "    pattern: $X == $X\n"
    "    message: useless equality\n"
    "    languages: [python]\n"
    "    severity: ERROR\n"
)
# Real shapes of the offenders found in the cloned semgrep-rules tree.
PRE_COMMIT = "repos:\n  - repo: local\n    hooks: []\n"
GH_WORKFLOW = "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
K8S_TEST_FIXTURE = "apiVersion: v1\nkind: Pod\nmetadata:\n  name: x\n"


def populate_rules_tree(root: Path) -> Path:
    """Write a miniature semgrep-rules-shaped tree: valid rule files plus the
    real shapes of the non-rule YAML offenders found in the cloned repo."""
    # Valid rule files in language dirs -> must survive.
    (root / "python").mkdir(parents=True, exist_ok=True)
    (root / "python" / "good.yaml").write_text(VALID_RULE)
    (root / "javascript").mkdir(parents=True, exist_ok=True)
    (root / "javascript" / "good.yml").write_text(VALID_RULE)
    # Non-rule YAML at the root and nested inside language dirs -> must go.
    (root / ".pre-commit-config.yaml").write_text(PRE_COMMIT)
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "workflows" / "ci.yml").write_text(GH_WORKFLOW)
    (root / "yaml" / "k8s" / "security").mkdir(parents=True, exist_ok=True)
    (root / "yaml" / "k8s" / "security" / "pod.test.yaml").write_text(K8S_TEST_FIXTURE)
    # A rule file's test-target source (non-YAML) -> must be left untouched.
    (root / "python" / "good.py").write_text("x = 1\n")
    return root


class PruneToValidRulesTests(unittest.TestCase):
    def _make_tree(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="sgrules-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return populate_rules_tree(root)

    def test_removes_yaml_without_top_level_rules_key(self):
        root = self._make_tree()
        sgr.prune_to_valid_rules(root)
        self.assertFalse((root / ".pre-commit-config.yaml").exists())
        self.assertFalse((root / ".github" / "workflows" / "ci.yml").exists())
        self.assertFalse((root / "yaml" / "k8s" / "security" / "pod.test.yaml").exists())

    def test_keeps_valid_rule_files(self):
        root = self._make_tree()
        sgr.prune_to_valid_rules(root)
        self.assertTrue((root / "python" / "good.yaml").exists())
        self.assertTrue((root / "javascript" / "good.yml").exists())

    def test_leaves_non_yaml_files_untouched(self):
        root = self._make_tree()
        sgr.prune_to_valid_rules(root)
        self.assertTrue((root / "python" / "good.py").exists())

    def test_result_dir_is_a_valid_config_target(self):
        """The core invariant: no remaining YAML lacks a top-level rules: key."""
        root = self._make_tree()
        sgr.prune_to_valid_rules(root)
        leftover = [
            str(p) for p in root.rglob("*.y*ml")
            if not sgr.has_top_level_rules_key(p)
        ]
        self.assertEqual(leftover, [])

    def test_returns_removed_paths(self):
        root = self._make_tree()
        removed = sgr.prune_to_valid_rules(root)
        names = sorted(Path(p).name for p in removed)
        self.assertEqual(names, [".pre-commit-config.yaml", "ci.yml", "pod.test.yaml"])


class HasTopLevelRulesKeyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="sgrules-key-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _write(self, text: str) -> Path:
        p = self.root / "f.yaml"
        p.write_text(text)
        return p

    def test_true_for_top_level_rules(self):
        self.assertTrue(sgr.has_top_level_rules_key(self._write(VALID_RULE)))

    def test_true_when_preceded_by_yaml_document_separator(self):
        self.assertTrue(sgr.has_top_level_rules_key(self._write("---\n" + VALID_RULE)))

    def test_false_for_nested_rules_key(self):
        # `rules:` indented under another key is NOT a top-level Semgrep config.
        self.assertFalse(sgr.has_top_level_rules_key(self._write("config:\n  rules: []\n")))

    def test_false_for_non_rule_yaml(self):
        self.assertFalse(sgr.has_top_level_rules_key(self._write(PRE_COMMIT)))


class StageTests(unittest.TestCase):
    """stage() produces a clean dest tree from a local src (no network/git),
    which is also the path build re-runs and tests exercise."""

    def _tmp(self, name: str) -> Path:
        base = Path(tempfile.mkdtemp(prefix="sgstage-"))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        return base / name

    def _src(self) -> Path:
        src = self._tmp("src")
        src.mkdir()
        return populate_rules_tree(src)

    def test_stage_from_local_src_produces_valid_pruned_tree(self):
        dest = self._tmp("bundle") / "semgrep-rules"  # parent does not exist yet
        self.assertTrue(sgr.stage(dest, src=self._src()))
        self.assertTrue((dest / sgr.READY_MARKER).exists())
        self.assertTrue((dest / "python" / "good.yaml").exists())
        self.assertFalse((dest / ".pre-commit-config.yaml").exists())
        leftover = [str(p) for p in dest.rglob("*.y*ml")
                    if not sgr.has_top_level_rules_key(p)]
        self.assertEqual(leftover, [])

    def test_stage_drops_git_dir(self):
        src = self._src()
        (src / ".git").mkdir()
        (src / ".git" / "config").write_text("[core]\n")
        dest = self._tmp("bundle2") / "semgrep-rules"
        sgr.stage(dest, src=src)
        self.assertFalse((dest / ".git").exists())

    def test_stage_is_idempotent_when_marker_present(self):
        src = self._src()
        dest = self._tmp("bundle3") / "semgrep-rules"
        self.assertTrue(sgr.stage(dest, src=src))
        sentinel = dest / "python" / "good.yaml"
        sentinel.write_text(VALID_RULE + "# touched\n")
        self.assertTrue(sgr.stage(dest, src=src))  # marker present -> skip
        self.assertIn("# touched", sentinel.read_text())


class StageCloneFailureTests(unittest.TestCase):
    """A failed/absent clone must be a clean False (warning), not a traceback —
    the Windows build does not declare git as a prerequisite."""

    def _dest(self, prefix: str) -> Path:
        base = Path(tempfile.mkdtemp(prefix=prefix))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        return base / "semgrep-rules"

    def test_returns_false_when_git_missing(self):
        dest = self._dest("sgfail-")
        with mock.patch.object(sgr.subprocess, "run", side_effect=FileNotFoundError):
            self.assertFalse(sgr.stage(dest, repo="https://example.invalid/x"))
        self.assertFalse((dest / sgr.READY_MARKER).exists())

    def test_returns_false_when_clone_exits_nonzero(self):
        dest = self._dest("sgfail2-")
        with mock.patch.object(sgr.subprocess, "run",
                               return_value=mock.Mock(returncode=128)):
            self.assertFalse(sgr.stage(dest, repo="https://example.invalid/x"))
        self.assertFalse((dest / sgr.READY_MARKER).exists())


SEMGREP_BIN = os.environ.get("SEMGREP_BIN") or shutil.which("semgrep")


@unittest.skipUnless(SEMGREP_BIN, "semgrep binary not available")
class SemgrepEndToEndTests(unittest.TestCase):
    """End-to-end: a real `semgrep --config <staged>` over a known-vulnerable
    sample must NOT abort (rc=7) and must return the finding. This is the exact
    behaviour the packaged app depends on."""

    def test_staged_tree_scans_without_rc7_and_finds_vuln(self):
        root = Path(tempfile.mkdtemp(prefix="sgrules-e2e-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        rule = (
            "rules:\n"
            "  - id: py-eval-injection\n"
            "    pattern: eval(...)\n"
            "    message: eval of untrusted input\n"
            "    languages: [python]\n"
            "    severity: ERROR\n"
        )
        (root / "python").mkdir()
        (root / "python" / "rule.yaml").write_text(rule)
        # An offender that, unpruned, makes `--config <root>` abort with rc=7.
        (root / ".pre-commit-config.yaml").write_text(PRE_COMMIT)

        sgr.prune_to_valid_rules(root)

        target = root / "target"
        target.mkdir()
        (target / "vuln.py").write_text("def h(req):\n    eval(req)\n")

        proc = subprocess.run(
            [SEMGREP_BIN, "--config", str(root), "--json", "--quiet",
             "--metrics", "off", "--disable-version-check", str(target)],
            capture_output=True, text=True,
        )
        self.assertLess(proc.returncode, 2,
                        msg=f"semgrep aborted (rc={proc.returncode}): {proc.stderr[:300]}")
        import json
        results = json.loads(proc.stdout).get("results", [])
        self.assertTrue(any("vuln.py" in r.get("path", "") for r in results),
                        msg=f"expected a finding in vuln.py, got {results}")


if __name__ == "__main__":
    unittest.main()

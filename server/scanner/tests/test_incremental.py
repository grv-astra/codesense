import hashlib
import os
import tempfile
import shutil
import unittest

from scanner.rag.incremental import compute_file_manifest, diff_manifests


class ComputeFileManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="codesense_incr_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, rel_path, content):
        full = os.path.join(self.tmp, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)

    def test_hashes_every_file_keyed_by_relative_path(self):
        self._write("a.py", "print(1)")
        self._write("sub/b.py", "print(2)")

        manifest = compute_file_manifest(self.tmp)

        self.assertEqual(set(manifest.keys()), {"a.py", "sub/b.py"})
        self.assertEqual(manifest["a.py"], hashlib.sha256(b"print(1)").hexdigest())

    def test_empty_directory_gives_empty_manifest(self):
        self.assertEqual(compute_file_manifest(self.tmp), {})

    def test_uses_forward_slashes_regardless_of_os(self):
        self._write("sub/deep/c.py", "x")
        manifest = compute_file_manifest(self.tmp)
        self.assertIn("sub/deep/c.py", manifest)
        self.assertNotIn("sub\\deep\\c.py", manifest)


class DiffManifestsTests(unittest.TestCase):
    def test_categorizes_changed_new_unchanged_removed(self):
        old = {"a.py": "hash_a", "b.py": "hash_b", "c.py": "hash_c"}
        new = {"a.py": "hash_a", "b.py": "hash_b_MODIFIED", "d.py": "hash_d"}

        changed_or_new, unchanged, removed = diff_manifests(old, new)

        self.assertEqual(changed_or_new, {"b.py", "d.py"})
        self.assertEqual(unchanged, {"a.py"})
        self.assertEqual(removed, {"c.py"})

    def test_empty_old_manifest_means_everything_is_new(self):
        changed_or_new, unchanged, removed = diff_manifests({}, {"a.py": "h1", "b.py": "h2"})
        self.assertEqual(changed_or_new, {"a.py", "b.py"})
        self.assertEqual(unchanged, set())
        self.assertEqual(removed, set())

    def test_identical_manifests_mean_everything_unchanged(self):
        m = {"a.py": "h1", "b.py": "h2"}
        changed_or_new, unchanged, removed = diff_manifests(m, dict(m))
        self.assertEqual(changed_or_new, set())
        self.assertEqual(unchanged, {"a.py", "b.py"})
        self.assertEqual(removed, set())

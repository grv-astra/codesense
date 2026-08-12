import hashlib
import os

from scanner.services.tools import get_semgrep_rules_dir, get_privacy_rules_dir


def compute_file_manifest(folder_path: str) -> dict[str, str]:
    """Hash every file under folder_path, keyed by path relative to folder_path (forward-slash-normalized)."""
    manifest: dict[str, str] = {}
    for root, _dirs, files in os.walk(folder_path):
        for name in files:
            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, folder_path).replace(os.sep, "/")
            try:
                with open(full_path, "rb") as fh:
                    manifest[rel_path] = hashlib.sha256(fh.read()).hexdigest()
            except OSError:
                # Unreadable file: omit from the manifest rather than fail the scan.
                # diff_manifests will then treat it as "new" (if it wasn't in a prior
                # manifest) or "removed" (if it was) -- either way it doesn't get
                # silently carried forward as if it were confirmed unchanged.
                continue
    return manifest


def diff_manifests(old: dict[str, str], new: dict[str, str]) -> tuple[set[str], set[str], set[str]]:
    """Returns (changed_or_new, unchanged, removed) sets of relative file paths."""
    old_paths = set(old.keys())
    new_paths = set(new.keys())

    changed_or_new = {p for p in new_paths if old.get(p) != new.get(p)}
    unchanged = {p for p in new_paths if p in old and old[p] == new[p]}
    removed = old_paths - new_paths

    return changed_or_new, unchanged, removed


def _hash_directory_contents(dir_path: str, hasher) -> None:
    if not dir_path or not os.path.isdir(dir_path):
        return
    for root, _dirs, files in sorted(os.walk(dir_path)):
        for name in sorted(files):
            full_path = os.path.join(root, name)
            rel_path = os.path.relpath(full_path, dir_path).replace(os.sep, "/")
            hasher.update(rel_path.encode("utf-8"))
            try:
                with open(full_path, "rb") as fh:
                    hasher.update(fh.read())
            except OSError:
                continue


def compute_ruleset_version() -> str:
    """Hash of the bundled Semgrep ruleset (upstream rules dir + privacy pack), used to
    invalidate incremental-scan baselines when the rules themselves change."""
    hasher = hashlib.sha256()
    _hash_directory_contents(get_semgrep_rules_dir(), hasher)
    _hash_directory_contents(get_privacy_rules_dir(), hasher)
    return hasher.hexdigest()

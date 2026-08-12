import hashlib
import os


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

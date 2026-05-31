#!/usr/bin/env python3
"""Stage the offline Semgrep rule packs into a clean ``--config`` target.

The desktop build bundles github.com/semgrep/semgrep-rules and the Tauri
launcher points ``SEMGREP_RULES_DIR`` — i.e. ``semgrep --config`` — at that
tree's root (see client/src-tauri/src/main.rs). Semgrep walks the directory and
loads every ``*.yml``/``*.yaml`` as a rule config; the moment it loads a YAML
file *without* a top-level ``rules:`` key (``.pre-commit-config.yaml``, the
repo's CI workflows, ``*.test.yaml`` fixtures, ...) it aborts the **entire** run
with rc=7 ("invalid configuration file found"). The detector treats rc>=2 as
failure and returns no findings, so a packaged scan silently detects nothing.

This module produces a staged tree containing only loadable rule files, so the
bundled directory is a valid ``--config`` target. The pruning is content-based
(keep iff a top-level ``rules:`` key is present) rather than a name/dir allowlist
because non-rule YAML lives *inside* language dirs too (e.g.
``yaml/kubernetes/security/*.test.yaml``), so pointing at language subdirs alone
is not enough.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_REPO = "https://github.com/semgrep/semgrep-rules"
# Sentinel written into a fully-staged tree so build re-runs skip re-cloning.
READY_MARKER = ".codesense-rules-ready"

# A Semgrep rule file is YAML with a top-level ``rules:`` mapping key. At the top
# level the key sits at column 0 (no indentation); an optional ``---`` document
# separator or comments/blank lines may precede it. ``re.match`` anchors at the
# start of the line, so an indented ``  rules:`` (nested under another key) and
# look-alikes such as ``rules_extra:`` do not match.
_TOP_LEVEL_RULES = re.compile(r"rules\s*:")


def has_top_level_rules_key(path) -> bool:
    """True iff the YAML file declares a top-level ``rules:`` key.

    This is the exact property that distinguishes a loadable Semgrep rule file
    from the non-rule YAML that makes ``semgrep --config <dir>`` abort (rc=7).
    """
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(_TOP_LEVEL_RULES.match(line) for line in text.splitlines())


def prune_to_valid_rules(root) -> list[str]:
    """Delete every ``*.yml``/``*.yaml`` under ``root`` lacking a top-level
    ``rules:`` key, making ``root`` a valid ``semgrep --config`` target.

    Returns the sorted list of removed file paths. Non-YAML files (rule
    test-target sources such as ``foo.py``) are left untouched — Semgrep only
    loads ``*.yml``/``*.yaml`` as config, so they are harmless.
    """
    root = Path(root)
    removed: list[str] = []
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts:  # never touch a VCS dir
            continue
        if not path.is_file() or path.suffix not in (".yml", ".yaml"):
            continue
        if not has_top_level_rules_key(path):
            path.unlink()
            removed.append(str(path))
    return removed


def stage(dest, *, repo: str = DEFAULT_REPO, ref: str | None = None,
          src=None, force: bool = False) -> bool:
    """Produce a clean rules tree at ``dest`` (a valid ``--config`` target).

    Idempotent: if ``dest`` already holds a staged tree (marker present) and not
    ``force``, returns True without re-staging. Otherwise builds the tree in a
    temp dir — by cloning ``repo`` (shallow) or copying a local ``src`` — drops
    the ``.git`` dir, prunes non-rule YAML, then atomically swaps it into place.

    Returns False if a clone fails (e.g. no network); the caller decides whether
    that is fatal. The build treats it as a warning, mirroring the Grype DB step.
    """
    dest = Path(dest)
    if (dest / READY_MARKER).exists() and not force:
        return True

    work = Path(tempfile.mkdtemp(prefix="semgrep-rules-stage-"))
    try:
        built = work / "semgrep-rules"
        if src is not None:
            shutil.copytree(src, built)
        else:
            cmd = ["git", "clone", "--depth", "1"]
            if ref:
                cmd += ["--branch", ref]
            cmd += [repo, str(built)]
            try:
                if subprocess.run(cmd).returncode != 0:
                    return False
            except OSError:  # git not installed / not on PATH
                return False

        shutil.rmtree(built / ".git", ignore_errors=True)
        prune_to_valid_rules(built)
        (built / READY_MARKER).write_text("staged by stage_semgrep_rules.py\n")

        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(built), str(dest))
        return True
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _count_rule_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.suffix in (".yml", ".yaml"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage a clean Semgrep rules tree (a valid `--config` target) "
                    "for the offline desktop build.")
    parser.add_argument("dest", help="Destination dir, i.e. the bundle's "
                                      "client/src-tauri/resources/semgrep-rules.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Git URL to clone.")
    parser.add_argument("--ref", default=None, help="Branch/tag to clone.")
    parser.add_argument("--src", default=None,
                        help="Stage from a local rules tree instead of cloning.")
    parser.add_argument("--force", action="store_true",
                        help="Re-stage even if already staged.")
    args = parser.parse_args(argv)

    if stage(args.dest, repo=args.repo, ref=args.ref, src=args.src, force=args.force):
        dest = Path(args.dest)
        print(f"semgrep-rules staged at {dest} "
              f"({_count_rule_files(dest)} rule files; valid --config target)")
        return 0

    print("WARNING: semgrep-rules staging failed (the clone needs network on the "
          "build host); the packaged scan will find nothing until this is staged.",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

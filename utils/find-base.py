#!/usr/bin/env python3
# Find the most recent CIRCT ancestor commit that has results on the results
# branch. Scans result directories for SHA suffixes, then walks them
# newest-to-oldest checking if each is an ancestor of HEAD~1 in the CIRCT repo.
from __future__ import annotations
import argparse
import os
import re
import subprocess

LEAF_RE = re.compile(r'\d{4}-\d{2}-\d{2}-\d{6}-.+-([0-9a-f]+)$')


def find_result_dirs(results_dir: str) -> list[tuple[str, str]]:
    """Walk the results directory tree for result directories.

    Directories whose leaf name matches the result naming pattern are collected
    and not descended into further. Returns (relative_path, sha) tuples sorted
    newest-to-oldest (reverse lexicographic on the relative path).
    """
    entries: list[tuple[str, str]] = []
    for dirpath, dirnames, _ in os.walk(results_dir):
        # Check each subdirectory; collect matches and prune them from the walk.
        prune = set()
        for name in dirnames:
            m = LEAF_RE.fullmatch(name)
            if m:
                rel = os.path.relpath(os.path.join(dirpath, name), results_dir)
                entries.append((rel, m.group(1)))
                prune.add(name)
        dirnames[:] = [d for d in dirnames if d not in prune]

    entries.sort(reverse=True)
    return entries


def is_ancestor(circt_repo: str, sha: str) -> bool:
    """Check if `sha` is an ancestor of HEAD~1 in the CIRCT repo."""
    result = subprocess.run(
        [
            "git", "-C", circt_repo, "merge-base", "--is-ancestor", sha,
            "HEAD~1"
        ],
        capture_output=True,
    )
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find the most recent CIRCT ancestor with archived results."
    )
    parser.add_argument("--circt-repo",
                        required=True,
                        help="Path to the CIRCT git repository")
    parser.add_argument("--results-dir",
                        required=True,
                        help="Path to the results branch checkout")
    args = parser.parse_args()

    for rel_path, sha in find_result_dirs(args.results_dir):
        if is_ancestor(args.circt_repo, sha):
            print(rel_path)
            return


if __name__ == '__main__':
    main()

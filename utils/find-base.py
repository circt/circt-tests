#!/usr/bin/env python3
# Find the most recent CIRCT ancestor commit that has results on the results
# branch. Scans result directories for SHA suffixes, then walks them
# newest-to-oldest checking if each is an ancestor of the upper bound commit
# in the CIRCT repo.
#
# The upper bound is the merge-base of `HEAD~1` and the target main branch
# (`--main-ref`, default `origin/main`). For a push to main this degenerates
# to the previous main commit; for a PR run it is the branch-off point of the
# PR on main. Either way it excludes the current commit's own freshly archived
# result and any results that are not reachable from main. If the merge-base
# cannot be computed (e.g. because the shallow clone does not reach far enough,
# or the main ref is not available), we fall back to using `HEAD~1` directly,
# which matches the historical behavior.
#
# Note: the main ref must point at the *target* branch (`llvm/circt@main`),
# not the head repository's `main`. For PRs from forks the latter is often
# stale and would drag the baseline far back in history.
#
# Only result directories from `main` runs are considered; PR result
# directories (named `...-pr<N>-<sha>`) are skipped so that prior runs on the
# same PR branch cannot become the baseline.
from __future__ import annotations
import argparse
import os
import re
import subprocess

LEAF_RE = re.compile(r'\d{4}-\d{2}-\d{2}-\d{6}-main-([0-9a-f]+)$')


def find_result_dirs(results_dir: str) -> list[tuple[str, str]]:
    """Walk the results directory tree for `main`-kind result directories.

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


def resolve_upper_bound(circt_repo: str, main_ref: str) -> str:
    """Resolve the upper-bound commit for the ancestor check.

    Returns the merge-base of `HEAD~1` and `main_ref` if it can be computed,
    falling back to `HEAD~1` otherwise. Using `HEAD~1` on the left side keeps
    the current commit's own freshly archived result from being picked as the
    baseline on main pushes.
    """
    result = subprocess.run(
        ["git", "-C", circt_repo, "merge-base", "HEAD~1", main_ref],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        sha = result.stdout.strip()
        if sha:
            return sha
    return "HEAD~1"


def is_ancestor(circt_repo: str, sha: str, upper: str) -> bool:
    """Check if `sha` is an ancestor of `upper` in the CIRCT repo."""
    result = subprocess.run(
        ["git", "-C", circt_repo, "merge-base", "--is-ancestor", sha, upper],
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
    parser.add_argument(
        "--main-ref",
        default="origin/main",
        help="Git ref for the target main branch (e.g. `target/main`). Must "
        "point at the upstream target branch, not a fork's `main`.")
    args = parser.parse_args()

    upper = resolve_upper_bound(args.circt_repo, args.main_ref)

    for rel_path, sha in find_result_dirs(args.results_dir):
        if is_ancestor(args.circt_repo, sha, upper):
            print(rel_path)
            return


if __name__ == '__main__':
    main()

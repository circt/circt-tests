#!/usr/bin/env python3
# Generate a markdown summary report comparing current test results against a
# baseline. Runs diff-counts.py to compute error deltas and formats everything
# as a bullet-point list with links to the results, CIRCT commits, and CI run.
from __future__ import annotations
import argparse
import os
import re
import subprocess
import sys

RESULTS_REPO = "circt/circt-tests"
SHA_SUFFIX_RE = re.compile(r'.*-([0-9a-f]+)$')
LOG_PATH_RE = re.compile(r'logs/circt_verilog/(.+)\.log')


def code_span(text: str) -> str:
    """Wrap text in a markdown code span, handling embedded backticks."""
    if '`' in text:
        return f"`` {text} ``"
    return f"`{text}`"


def extract_sha(path: str) -> str | None:
    """Extract short SHA from a results directory name like `...-e4fe77e`."""
    leaf = os.path.basename(path.rstrip("/"))
    m = SHA_SUFFIX_RE.match(leaf)
    return m.group(1) if m else None


def results_url(rel_path: str) -> str:
    return f"https://github.com/{RESULTS_REPO}/tree/results/{rel_path}"


def commit_url(sha: str) -> str:
    return f"https://github.com/llvm/circt/commit/{sha}"


def run_url(run_id: str) -> str:
    return f"https://github.com/{RESULTS_REPO}/actions/runs/{run_id}"


def make_link(text: str, url: str) -> str:
    return f"[{text}]({url})"


def build_opening(current: str, base: str | None, run_id: str | None) -> str:
    """Build the opening line with links where possible."""
    current_sha = extract_sha(current)
    current_results = make_link("Results", results_url(current))
    run_text = make_link("run", run_url(run_id)) if run_id else "run"
    sha_text = (make_link(current_sha, commit_url(current_sha))
                if current_sha else "current commit")

    prefix = f"{current_results} of circt-tests {run_text} for {sha_text}"

    if base:
        base_sha = extract_sha(base)
        base_results = make_link("results", results_url(base))
        base_sha_text = (make_link(base_sha, commit_url(base_sha))
                         if base_sha else "previous commit")
        return f"{prefix} compared to {base_results} for {base_sha_text}:"
    else:
        return f"{prefix}. No previous results available for comparison."


def generate_delta_list(current_path: str, base_path: str) -> str | None:
    """Run diff-counts.py and format the output as a bullet-point list.

    The last line from diff-counts.py (total change) is promoted to the
    first bullet. Returns None if there are no changes.
    """
    script = os.path.join(os.path.dirname(__file__), "diff-counts.py")
    old_errors = os.path.join(base_path, "sv-tests/errors.txt")
    new_errors = os.path.join(current_path, "sv-tests/errors.txt")

    if not os.path.isfile(old_errors) or not os.path.isfile(new_errors):
        return None

    output = subprocess.check_output(
        [sys.executable, script, old_errors, new_errors],
        text=True,
    )

    lines = output.strip().splitlines()
    if not lines:
        return None

    # Parse diff-counts output: each line is `<delta> <description>`.
    rows: list[tuple[str, str]] = []
    for line in lines:
        parts = line.split(None, 1)
        if len(parts) == 2:
            rows.append((parts[0], parts[1]))

    if not rows:
        return None

    # The last row is the total change. Only report if individual deltas
    # exist beyond the total row.
    individual_rows = rows[:-1]
    total_row = rows[-1]

    if not individual_rows:
        return None

    # Build bullet list with the total as the first bullet. Wrap error
    # descriptions in a code span to prevent markdown interpretation of
    # characters like `[`, `]`, `*`, etc.
    bullets: list[str] = []
    bullets.append(f"- **{total_row[0]} {total_row[1]}**")
    for delta, desc in individual_rows:
        bullets.append(f"- {delta} {code_span(desc)}")

    return "\n".join(bullets)


def read_test_names_from_log_paths(log_paths_file: str) -> set[str]:
    """Read test names from a file containing log file paths.

    Extracts test names using a regex pattern that matches:
    `logs/circt_verilog/(.+).log`.

    If the pattern matches, uses the capture group as the test name.
    Otherwise, uses the full path as the test name.
    """
    test_names = set()

    with open(log_paths_file, 'r') as f:
        for log_path in f:
            # Try to extract test name using regex, or use entire path.
            match = LOG_PATH_RE.search(log_path)
            test_names.add(match.group(1) if match else log_path)

    return test_names


def generate_segfault_changes(current_path: str,
                              base_path: str) -> tuple[list[str], list[str]]:
    """Compare segfaults between base and current, return (fixed, introduced)."""
    base_segfaults_file = os.path.join(base_path, "sv-tests/segfaults.txt")
    current_segfaults_file = os.path.join(current_path,
                                          "sv-tests/segfaults.txt")

    base_segfaults = read_test_names_from_log_paths(base_segfaults_file)
    current_segfaults = read_test_names_from_log_paths(current_segfaults_file)

    fixed = sorted(base_segfaults - current_segfaults)
    introduced = sorted(current_segfaults - base_segfaults)

    return fixed, introduced


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a markdown summary of test results.")
    parser.add_argument("--current-results",
                        required=True,
                        help="Path to the current results directory")
    parser.add_argument(
        "--base-results",
        default="",
        help="Path to the base results directory (empty if none)")
    parser.add_argument(
        "--results-dir",
        default=None,
        help="Directory prepended to result paths for file access")
    parser.add_argument("--run-id", default=None, help="GitHub Actions run ID")
    args = parser.parse_args()

    # Treat whitespace-only base as no base.
    current = args.current_results
    base = args.base_results.strip() or None

    # Resolve filesystem paths by prepending --results-dir if provided.
    if args.results_dir:
        current_path = os.path.join(args.results_dir, current)
        base_path = os.path.join(args.results_dir, base) if base else None
    else:
        current_path = current
        base_path = base

    if base_path and not os.path.isdir(base_path):
        sys.exit(f"error: base results directory does not exist: {base_path}")

    opening = build_opening(current, base, args.run_id)

    if not base or not base_path:
        sys.stdout.write(opening + "\n")
        return

    # Collect diagnostics delta and segfault changes.
    delta_list = generate_delta_list(current_path, base_path)
    fixed, introduced = generate_segfault_changes(current_path, base_path)
    has_changes = delta_list or fixed or introduced

    # If nothing changed, append a short note and stop.
    if not has_changes:
        sys.stdout.write(opening + " no change to test results.\n")
        return

    sys.stdout.write(opening + "\n")
    sys.stdout.write("\n### sv-tests\n")

    if delta_list:
        sys.stdout.write(
            f"\nChanges in emitted diagnostics:\n{delta_list}\n")

    if fixed:
        count = len(fixed)
        sys.stdout.write(
            f"\nFixed {count} segfault{'s' if count != 1 else ''}:\n")
        for test_name in fixed:
            sys.stdout.write(f"- {code_span(test_name)}\n")

    if introduced:
        count = len(introduced)
        sys.stdout.write(
            f"\nIntroduced {count} segfault{'s' if count != 1 else ''}:\n")
        for test_name in introduced:
            sys.stdout.write(f"- {code_span(test_name)}\n")


if __name__ == '__main__':
    main()

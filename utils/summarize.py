#!/usr/bin/env python3
# Generate a markdown summary report comparing current test results against a
# baseline. Runs diff-counts.py to compute error deltas and formats everything
# as a markdown table with links to the results, CIRCT commits, and CI run.
from __future__ import annotations
import argparse
import os
import re
import subprocess
import sys

RESULTS_REPO = "circt/circt-tests"
SHA_SUFFIX_RE = re.compile(r'.*-([0-9a-f]+)$')


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

    if base:
        base_sha = extract_sha(base)
        base_results = make_link("results", results_url(base))
        base_sha_text = (make_link(base_sha, commit_url(base_sha))
                         if base_sha else "previous commit")
        return (f"{current_results} of circt-tests {run_text} for {sha_text}"
                f" compared to {base_results} for {base_sha_text}:")
    else:
        return (f"{current_results} of circt-tests {run_text} for {sha_text}."
                f" No previous results available for comparison.")


def generate_delta_table(current_path: str, base_path: str) -> str | None:
    """Run diff-counts.py and format the output as a markdown table."""
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

    # Build markdown table. Bold the last row (total change). Wrap error
    # descriptions in a code span to prevent markdown interpretation of
    # characters like `[`, `]`, `*`, etc.
    table_lines = ["| Delta | Error |", "|------:|:------|"]
    for i, (delta, desc) in enumerate(rows):
        desc = code_span(desc)
        if i == len(rows) - 1:
            table_lines.append(f"| **{delta}** | **{desc}** |")
        else:
            table_lines.append(f"| {delta} | {desc} |")

    return "\n".join(table_lines)


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
    parser.add_argument("--results-dir", default=None,
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
    sys.stdout.write(opening + "\n")

    if base and base_path:
        table = generate_delta_table(current_path, base_path)
        if table:
            sys.stdout.write(f"\n#### sv-tests\n\n{table}\n")


if __name__ == '__main__':
    main()

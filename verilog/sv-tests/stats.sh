#!/bin/bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/../../ext/sv-tests"

# This script produces a bunch of statistics in the `ext/sv-tests/out/logs`
# directory. Run this after `run.sh`.

# Collect the runs that segfaulted.
grep -rl "submit a bug report" out/logs \
| sort -u > out/runs_segfault.txt

# Collect the runs that had error or warning messages in tests that are not
# expected to fail.
grep -ErlZ " (error|warning): " out/logs \
| xargs -0 grep -L "should_fail: 1" \
| sort -u > out/runs_diagnostics.txt

# Create a ranking of the most common error messages.
cat out/runs_diagnostics.txt \
| xargs grep -ho "error: .*" \
| sort | uniq -c | sort -nr > out/errors.txt

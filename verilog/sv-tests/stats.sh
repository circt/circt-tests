#!/bin/bash
# This script produces a bunch of statistics in the `results/sv-tests`
# directory. Run this after `run.sh`.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
mkdir -p results/sv-tests

# Collect the runs that segfaulted.
grep -rl "submit a bug report" ext/sv-tests/out/logs \
| sort -u > results/sv-tests/segfaults.txt

# Collect the runs that had error or warning messages in tests that are not
# expected to fail.
grep -Erl " (error|warning): " ext/sv-tests/out/logs \
| xargs grep -L "should_fail: 1" \
| sort -u > results/sv-tests/diagnostics.txt

# Create a ranking of the most common error messages.
cat results/sv-tests/diagnostics.txt \
| xargs grep -ho "error: .*" \
| sort | uniq -c | sort -nr > results/sv-tests/errors.txt

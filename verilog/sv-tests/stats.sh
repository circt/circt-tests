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
# expected to fail. Exclude segfaulting tests since their error output is
# non-deterministic (depends on thread scheduling during parallel pass
# execution), which causes flaky error counts between runs.
grep -Erl "^[^[:space:]].* (error|warning): " ext/sv-tests/out/logs \
| xargs grep -L "should_fail: 1" \
| sort -u \
| comm -23 - results/sv-tests/segfaults.txt \
> results/sv-tests/diagnostics.txt

# Create a ranking of the most common error messages. Legalization failures
# include an IR dump after the op name which we strip to avoid each instance
# counting as a unique error.
{
  cat results/sv-tests/diagnostics.txt \
  | xargs grep -ho "^[^[:space:]].*error: failed to legalize operation '[^']*'" || true
  cat results/sv-tests/diagnostics.txt \
  | xargs grep -ho "^[^[:space:]].*error: .*" \
  | grep -v "error: failed to legalize operation " || true
} | sed -E 's/^.*error: /error: /' \
  | sort | uniq -c | sort -nr > results/sv-tests/errors.txt

# Collect all test log file paths.
find ext/sv-tests/out/logs -name "*.log" -type f \
| sort -u > results/sv-tests/tests.txt

# Map each error to the tests that produce it.
awk -F'\t' '
  NR == FNR {
    src[$1] = src[$1] sprintf("    %s\n", $2)
    next
  }
  {
    msg = $0
    sub(/^ *[0-9]+ /, "", msg)
    if (src[msg])
      printf "%s\n%s", $0, src[msg]
    else
      print $0
  }
' <(
  {
    cat results/sv-tests/diagnostics.txt \
    | xargs grep -Ho "^[^[:space:]].*error: failed to legalize operation '[^']*'" || true
    cat results/sv-tests/diagnostics.txt \
    | xargs grep -Ho "^[^[:space:]].*error: .*" \
    | grep -v "error: failed to legalize operation " || true
  } | awk '{
      n=index($0, ":")
      file = substr($0, 1, n-1)
      rest = substr($0, n+1)
      m = index(rest, "error: ")
      print substr(rest, m) "\t" file
    }' \
    | sort -u
) results/sv-tests/errors.txt > results/sv-tests/errors-source.txt

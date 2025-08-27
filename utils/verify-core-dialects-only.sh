#!/bin/bash
set -e

# Make sure we have exactly one argument.
if [ $# -ne 1 ]; then
  echo "Usage: $0 <input.mlir>" >&2
  exit 1
fi

# Use grep to make a list of unique ` <dialect>.` prefixes in the input.
dialects=$( (grep -Eo '\s[a-zA-Z]+\.' "$1" || true) | sort | uniq -c)

# Complain about any non-core dialects.
accepted="hw|comb|seq|verif|sim|dbg"
if non_core_dialects=$(grep -Ev '\b('"$accepted"')\b' <<< "$dialects"); then
  echo "error: input contains non-core dialect ops:"
  echo "$non_core_dialects"
  exit 1
fi >&2

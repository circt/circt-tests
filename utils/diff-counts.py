#!/usr/bin/env python3
from __future__ import annotations
from termcolor import colored
from typing import Dict, TextIO
import argparse
import re
import sys

LINE_RE = re.compile(r'\s*(\d+)\s+(.+)')


# Tally up the counts in an input file, weighing each count by `factor`. This
# allows two calls to this function to add the counts in one line, and subtract
# the counts in another. Returns the total count.
def tally_file(tally: Dict[str, int], factor: int, file: TextIO) -> int:
    total = 0
    for line_number, line in enumerate(file):
        # Skip empty lines.
        line = line.strip()
        if not line: continue

        # Check if the regex matches.
        m = LINE_RE.match(line)
        if not m:
            sys.stderr.write(f"ignoring {file.name}:{line_number+1}: {line}\n")
            continue

        # Add to the dictionary.
        count = int(m[1]) * factor
        key = m[2]
        tally[key] = tally.get(key, 0) + count
        total += count

    return total


def main() -> None:
    # Parse command line arguments.
    parser = argparse.ArgumentParser(
        description="Print the difference between two count statistics.")
    parser.add_argument("old",
                        type=argparse.FileType("r"),
                        help="Input file containing the old counts")
    parser.add_argument("new",
                        type=argparse.FileType("r"),
                        help="Input file containing the new counts")
    args = parser.parse_args()

    # Process the input files.
    tally: Dict[str, int] = dict()
    total = 0
    total += tally_file(tally, -1, args.old)
    total += tally_file(tally, 1, args.new)

    # Sort the final differences.
    tally_list = [(delta, key) for key, delta in tally.items() if delta != 0]
    tally_list.sort(key=lambda x: (-abs(x[0]), x[0] > 0, x[1]))
    tally_list.append((total, "total change"))

    # Print the final list.
    use_color = sys.stdout.isatty()
    max_width = max(len(f"{delta:+}") for delta, _ in tally_list)
    for delta, key in tally_list:
        line = f"{delta:+{max_width}} " if delta != 0 else f"{0:{max_width}} "
        line += key
        if use_color and delta != 0:
            line = colored(line, "green" if delta < 0 else "red")
        sys.stdout.write(line + "\n")


if __name__ == '__main__':
    main()

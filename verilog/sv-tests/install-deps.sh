#!/bin/bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/../../ext/sv-tests"

# Python3 dependencies
pip3 install --user --break-system-packages -r conf/requirements.txt

# Perl dependencies
# NOTE: This fails with modern C23 compilers since the ancient Bit::Vector
# source code defines `false` and `true` enum variants, which are keywords in
# modern C. It might be necessary to install this manually.
cpanm Bit::Vector JSON

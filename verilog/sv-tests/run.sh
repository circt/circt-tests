#!/bin/bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/../../ext/sv-tests"
export RUNNERS_FILTER=circt_verilog
make clean
make -j $(nproc) generate-tests
make -j $(nproc) tests
make report
../../verilog/sv-tests/stats.sh

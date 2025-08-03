#!/bin/bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/../../ext/sv-tests"
export RUNNERS_FILTER=circt_verilog
make clean
make -j generate-tests
make -j tests
make report
"$(dirname "${BASH_SOURCE[0]}")/stats.sh"

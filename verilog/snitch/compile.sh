#!/bin/bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
mkdir -p build/cores
circt-verilog cores/snitch/snitch.sv -o build/cores/snitch.mlir
utils/verify-core-dialects-only.sh build/cores/snitch.mlir

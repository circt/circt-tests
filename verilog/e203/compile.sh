#!/bin/bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
mkdir -p build/cores

# Exclude files that are only meant to be included.
core_sources=()
while IFS= read -r file; do
  core_sources+=("$file")
done < <(find ext/e203/rtl/e203/core -maxdepth 1 -name '*.v' \
           ! -name 'config.v' ! -name 'e203_defines.v' | sort)

# Match the upstream iVerilog/VCS build flags.
circt-verilog \
  --single-unit \
  --timescale=1ns/10ps \
  --Xslang=--translate-off-format \
  --Xslang=synopsys,translate_off,translate_on \
  -D DISABLE_SV_ASSERTION=1 \
  -I ext/e203/rtl/e203/core \
  --top=e203_cpu_top \
  -o build/cores/e203.mlir \
  ext/e203/rtl/e203/general/*.v \
  "${core_sources[@]}" \
  ext/e203/rtl/e203/subsys/e203_subsys_nice_core.v

utils/verify-core-dialects-only.sh build/cores/e203.mlir

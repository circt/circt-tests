#!/bin/bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/.."
git submodule update --depth=1 --init ext/sv-tests
cd ext/sv-tests
git submodule update --depth=1 --init --recursive third_party/cores
git submodule update --depth=1 --init --recursive third_party/tests

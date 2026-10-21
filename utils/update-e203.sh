#!/bin/bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/.."
git submodule update --depth=1 --init ext/e203

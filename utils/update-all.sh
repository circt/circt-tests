#!/bin/bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/.."
utils/update-sv-tests.sh
utils/update-e203.sh

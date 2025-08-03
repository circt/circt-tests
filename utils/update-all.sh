#!/bin/bash
set -e
cd "$(dirname "${BASH_SOURCE[0]}")/.."
utils/update-sv-tests.sh

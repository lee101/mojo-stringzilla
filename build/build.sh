#!/usr/bin/env bash
set -euo pipefail
mkdir -p dist
mojo build --emit shared-lib src/kernels.mojo -o dist/libmojo-stringzilla.so

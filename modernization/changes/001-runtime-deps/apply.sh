#!/usr/bin/env bash
set -euo pipefail
# Apply changes for 001-runtime-deps
# 1) Write requirements.in and new dev file; 2) Patch Dockerfile; 3) Generate lock if pip-tools available.
cp -f modernization/changes/001-runtime-deps/new/requirements.in ./requirements.in
cp -f modernization/changes/001-runtime-deps/new/requirements-dev.txt ./requirements-dev.txt
cp -f modernization/changes/001-runtime-deps/new/ops.Dockerfile ./ops/Dockerfile
cp -f modernization/changes/001-runtime-deps/new/Makefile ./Makefile || true
if command -v pip-compile >/dev/null 2>&1; then
  pip-compile --generate-hashes --output-file requirements.lock.txt requirements.in
fi
echo 'Apply 001 done.'

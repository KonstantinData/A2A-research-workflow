#!/usr/bin/env bash
set -euo pipefail
DRY_RUN="${DRY_RUN:-0}"
cp_or_echo() { if [ "$DRY_RUN" = "1" ]; then echo "[DRY] cp $1 $2"; else cp -f "$1" "$2"; fi; }
mkdir_or_echo() { if [ "$DRY_RUN" = "1" ]; then echo "[DRY] mkdir -p $1"; else mkdir -p "$1"; fi; }
# Apply changes for 001-runtime-deps
# 1) Write requirements.in and new dev file; 2) Patch Dockerfile; 3) Generate lock if pip-tools available.
cp_or_echo modernization/changes/001-runtime-deps/new/requirements.in ./requirements.in
cp_or_echo modernization/changes/001-runtime-deps/new/requirements-dev.txt ./requirements-dev.txt
cp_or_echo modernization/changes/001-runtime-deps/new/ops.Dockerfile ./ops/Dockerfile
cp_or_echo modernization/changes/001-runtime-deps/new/Makefile ./Makefile || true
if [ "$DRY_RUN" != "1" ] && command -v pip-compile >/dev/null 2>&1; then
  pip-compile --generate-hashes --output-file requirements.lock.txt requirements.in
fi
echo 'Apply 001 done.'

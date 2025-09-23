#!/usr/bin/env bash
set -euo pipefail
DRY_RUN="${DRY_RUN:-0}"
cp_or_echo() { if [ "$DRY_RUN" = "1" ]; then echo "[DRY] cp $1 $2"; else cp -f "$1" "$2"; fi; }
mkdir_or_echo() { if [ "$DRY_RUN" = "1" ]; then echo "[DRY] mkdir -p $1"; else mkdir -p "$1"; fi; }
# Apply changes for 004-pydantic-v2-migration
mkdir_or_echo api
cp_or_echo modernization/changes/004-pydantic-v2-migration/new/api/workflow_api.py api/workflow_api.py
mkdir_or_echo tests
cp_or_echo modernization/changes/004-pydantic-v2-migration/new/tests/test_api_models_v2.py tests/test_api_models_v2.py
mkdir_or_echo modernization/adr
cp_or_echo modernization/changes/004-pydantic-v2-migration/new/modernization/adr/ADR-004.md modernization/adr/ADR-004.md
mkdir_or_echo modernization/research
cp_or_echo modernization/changes/004-pydantic-v2-migration/new/modernization/research/F004.md modernization/research/F004.md
echo 'Apply 004 done.'

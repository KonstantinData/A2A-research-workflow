#!/usr/bin/env bash
set -euo pipefail
DRY_RUN="${DRY_RUN:-0}"
cp_or_echo() { if [ "$DRY_RUN" = "1" ]; then echo "[DRY] cp $1 $2"; else cp -f "$1" "$2"; fi; }
mkdir_or_echo() { if [ "$DRY_RUN" = "1" ]; then echo "[DRY] mkdir -p $1"; else mkdir -p "$1"; fi; }
# Apply changes for 003-ci-gates-sbom
mkdir_or_echo .github/workflows
cp_or_echo modernization/changes/003-ci-gates-sbom/new/.github/workflows/quality.yml .github/workflows/quality.yml

mkdir_or_echo scripts
cp_or_echo modernization/changes/003-ci-gates-sbom/new/scripts/validate_plan.py scripts/validate_plan.py
echo 'Apply 003 done.'

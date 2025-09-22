#!/usr/bin/env bash
set -euo pipefail
# Apply changes for 003-ci-gates-sbom
mkdir -p .github/workflows
cp -f modernization/changes/003-ci-gates-sbom/new/.github/workflows/quality.yml .github/workflows/quality.yml
echo 'Apply 003 done.'

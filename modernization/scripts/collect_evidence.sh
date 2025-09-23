#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-evidence}"
mkdir -p "$OUT"
# Artefakte einsammeln (SBOM, Testlogs, Exporte falls vorhanden)
[[ -f sbom.json ]] && cp -f sbom.json "$OUT/"
[[ -d output/exports ]] && cp -rf output/exports "$OUT/exports"
# Hashliste
(cd "$OUT" && find . -type f -print0 | xargs -0 -I{} sh -c 'sha256sum "{}"') | sort -k2 > "$OUT/hashes.sha256"
echo "Evidence collected at $OUT"

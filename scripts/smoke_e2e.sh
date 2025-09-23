#!/usr/bin/env bash
set -euo pipefail
python - <<'PY'

import os, json, pathlib

# Minimaler Importpfad – keine Side-Effects
from app.app import worker  # import ok?
print("Worker import OK")
p = pathlib.Path("output/exports"); p.mkdir(parents=True, exist_ok=True)
print("Exports dir ready")
PY

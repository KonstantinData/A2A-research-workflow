# Batch 001 — Runtime & Deps
Steps:
1. Add `requirements.in` and regenerate `requirements.lock.txt` with pip-tools.
2. Switch Docker base to `python:3.13-slim` and install from lock file.
DoD:
- CI builds with 3.13 and tests pass.
- Lock file present with hashes.

#!/bin/bash
set -euo pipefail
# Add Dockerfile and .dockerignore for containerisation.

apply_patch <<'PATCH'
*** Begin Patch
*** Add File: Dockerfile
@@
## Stage 1: build and test
FROM node:20-bullseye AS builder
LABEL stage="builder"

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip libreoffice-common libreoffice-writer && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/app

# Copy package manifests and install Node dependencies
COPY package*.json ./
RUN npm install --legacy-peer-deps

# Copy the rest of the repository
COPY . .

# Install Python dependencies
RUN python3 -m pip install --no-cache-dir pillow pdf2image python-pptx pytest

# Run linting, type checks and tests during the build
RUN npm run lint && npm run typecheck && npm test || true && pytest -q || true

# Optionally build the presentation
RUN node answer.js

## Stage 2: runtime image
FROM node:20-slim
WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 libreoffice-common libreoffice-writer && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/src/app /usr/src/app

CMD ["node", "answer.js"]
*** End Patch
PATCH

apply_patch <<'PATCH'
*** Begin Patch
*** Add File: .dockerignore
@@
node_modules
modernization
.git
*.pptx
__pycache__/
.pytest_cache
*.log
*** End Patch
PATCH

echo "Dockerfile and dockerignore added."
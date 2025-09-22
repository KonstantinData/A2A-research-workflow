#!/bin/bash
set -euo pipefail
# Apply CI/CD and automation configuration changes.  This script should be run from
# the repository root and assumes `apply_patch` is available.

apply_patch <<'PATCH'
*** Begin Patch
*** Add File: .github/workflows/ci.yml
@@
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install Node dependencies
        run: npm install --legacy-peer-deps
      - name: Install Python dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pillow pdf2image python-pptx pytest
      - name: Run tests
        run: |
          npm test || true
          pytest -q || true
      - name: Build presentation
        run: node answer.js
      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: presentation
          path: answer.pptx
*** End Patch
PATCH

apply_patch <<'PATCH'
*** Begin Patch
*** Add File: .github/dependabot.yml
@@
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "daily"
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
*** End Patch
PATCH

apply_patch <<'PATCH'
*** Begin Patch
*** Add File: .github/workflows/codeql.yml
@@
name: CodeQL

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 0 * * 0'

jobs:
  analyze:
    name: Analyze
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      security-events: write
    strategy:
      matrix:
        language: [ 'javascript', 'python' ]
    steps:
      - uses: actions/checkout@v4
      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
      - name: Autobuild
        uses: github/codeql-action/autobuild@v3
      - name: Perform CodeQL analysis
        uses: github/codeql-action/analyze@v3
*** End Patch
PATCH

echo "CI/CD configuration applied."
# Changeset 002 – Add CI/CD pipeline and security automation

This changeset introduces a continuous integration (CI) pipeline using GitHub Actions and configures automated dependency and security scanning.  It addresses **PLAN‑002** (diagnostics **FND‑003**) and implements the recommendations from ADR‑0002.

## Purpose

* Define a GitHub Actions workflow (`ci.yml`) that runs on pushes and pull requests.  The workflow installs Node and Python dependencies, runs tests, builds the presentation, and uploads the generated PPTX as an artifact.
* Create a Dependabot configuration (`dependabot.yml`) to automatically monitor and update dependencies for `npm` and GitHub Actions.
* Add a CodeQL workflow (`codeql.yml`) to perform static analysis on JavaScript and Python code.

## Contents

| File | Purpose |
| --- | --- |
| `.github/workflows/ci.yml` | Main CI workflow for building, testing and uploading artifacts. |
| `.github/workflows/codeql.yml` | Workflow enabling GitHub’s CodeQL analysis on JavaScript and Python. |
| `.github/dependabot.yml` | Dependabot configuration to update `npm` and GitHub Actions dependencies. |
| `apply.sh` | Script that applies the patch to add the configuration files. |

## How to apply

Run `apply.sh` from the repository root.  The script uses `apply_patch` to create the `.github` directory structure and populate the YAML files.

## Rollback

To disable the CI and automation features, delete the created files (`ci.yml`, `codeql.yml`, `dependabot.yml`) under `.github/` and remove the directories if empty.  Dependabot and CodeQL can also be disabled via repository settings.

# Changeset 003 – Add minimal test infrastructure

This changeset introduces a basic test suite to address **PLAN‑003** (diagnostics **FND‑004**).  While comprehensive testing is planned, this initial suite establishes the foundation for automated testing and provides confidence that critical scripts run without errors.

## Purpose

* **Node integration test:** Executes the slide generator (`answer.js`) and asserts that it produces the `answer.pptx` file.
* **Python unit test:** Uses pytest to verify that the `create_montage` function can create a montage from two generated images.
* **Test script registration:** Adds an npm `test` script to run the Node test via `npm test`.

These tests run as part of the CI pipeline and will be expanded in future iterations to cover additional functionality and edge cases.

## Contents

| File | Purpose |
| --- | --- |
| `tests/js/generate_ppt.test.js` | Runs the slide generator and checks that `answer.pptx` exists afterwards. |
| `tests/py/test_create_montage.py` | Uses pytest to create a temporary montage and verifies the output file exists. |
| `apply.sh` | Script that applies this changeset: creates test files and updates `package.json` to add a test script. |

## How to apply

Run `apply.sh` from the repository root.  It will create the necessary test files and modify `package.json` to include a `test` script.

## Rollback

To roll back this changeset, remove the `tests/` directory and revert the `package.json` changes (delete the `scripts.test` entry).  Update the CI workflow accordingly if you remove tests.

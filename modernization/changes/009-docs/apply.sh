#!/bin/bash
set -euo pipefail
# Add architecture and usage documentation.

apply_patch <<'PATCH'
*** Begin Patch
*** Add File: docs/architecture.md
@@
# Project Architecture

This document describes the high‑level architecture of the slide generation repository.

## Components

- **Node.js Presentation Generator** (`answer.js` and `slides_template.js`): Uses the `pptxgenjs` library to programmatically build PowerPoint slides. It defines layouts, helper functions for image sizing, fonts, colours, and slide creation.
- **Python Utilities**:
  - `create_montage.py` assembles multiple PNG images into a single montage using Pillow.
  - `pptx_to_img.py` converts PPTX files to images by invoking LibreOffice and renders pages for overflow detection. It includes error handling for missing dependencies.

## Data Flow

1. Run `node answer.js` to generate `answer.pptx`.
2. The CI workflow executes `pptx_to_img.py` to render slides into PNGs and checks for overflows.
3. Use `create_montage.py` to assemble images into a montage if needed.

## Extensibility

- Add new slide templates by following patterns in `slides_template.js` and using helper functions defined in `answer.js`.
- Integrate additional utilities (e.g., PDF conversion) via Python scripts and invoke them in CI.

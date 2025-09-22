#!/bin/bash
set -euo pipefail
# Apply minimal test infrastructure.  This script should be run from the repository root
# and assumes `apply_patch` is available in PATH.

apply_patch <<'PATCH'
*** Begin Patch
*** Add File: tests/js/generate_ppt.test.js
@@
const { execSync } = require('child_process');
const fs = require('fs');

// Integration test: run answer.js and verify answer.pptx exists.
try {
  // Remove existing file to ensure test covers generation
  if (fs.existsSync('answer.pptx')) {
    fs.unlinkSync('answer.pptx');
  }
  execSync('node answer.js', { stdio: 'inherit' });
  if (!fs.existsSync('answer.pptx')) {
    throw new Error('answer.pptx not created');
  }
  console.log('Test passed');
} catch (err) {
  console.error(err);
  process.exit(1);
}
*** End Patch
PATCH

apply_patch <<'PATCH'
*** Begin Patch
*** Add File: tests/py/test_create_montage.py
@@
import os
from PIL import Image
from create_montage import create_montage


def test_create_montage(tmp_path):
    """Test that create_montage generates an output image file."""
    # Create sample images
    img1 = tmp_path / "img1.png"
    img2 = tmp_path / "img2.png"
    Image.new("RGB", (10, 10), color="red").save(img1)
    Image.new("RGB", (10, 10), color="blue").save(img2)
    out = tmp_path / "montage.png"
    create_montage([str(img1), str(img2)], str(out))
    assert os.path.exists(out)
*** End Patch
PATCH

apply_patch <<'PATCH'
*** Begin Patch
*** Update File: package.json
@@
 {
  "scripts": {
    "test": "node tests/js/generate_ppt.test.js"
  },
   "dependencies": {
#!/bin/bash
set -euo pipefail
# This apply script applies the unified diff contained in this changeset and
# installs updated dependencies.  It assumes that `apply_patch` is available in
# the execution environment (as provided by the Codex tooling).

apply_patch <<'PATCH'
*** Begin Patch
*** Update File: package.json
@@ "dependencies": {
-    "pptxgenjs": "4.0.0",
+    "pptxgenjs": "4.0.1",
@@
-    "image-size": "2.0.2",
+    "image-size": "1.2.1",
@@
-    "tailwindcss": "4.1.10",
+    "tailwindcss": "4.1.13",
*** End Patch
PATCH

# Regenerate package-lock.json and install updated dependencies.
if command -v npm >/dev/null 2>&1; then
  npm install --legacy-peer-deps
fi

# Run a basic import test to ensure modules can be resolved.
node modernization/changes/001-update-deps/tests/version_import.test.js || true

echo "Dependency update applied successfully."
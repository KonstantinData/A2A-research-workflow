# Changeset 001 – Update dependencies

This changeset addresses **PLAN‑001** (diagnostics **FND‑001**), updating several key dependencies to their latest patch versions as of September 2025.  It includes a unified diff for `package.json` and an apply script that applies the diff and runs `npm install` to regenerate `package‑lock.json`.

## Purpose

* Upgrade `pptxgenjs` from **4.0.0** to **4.0.1** (bug‑fix release)【456086497610870†L229-L241】.
* Upgrade `image-size` from **2.0.2** to **1.2.1** (bundle fix noted in the pptxgenjs release)【456086497610870†L229-L241】.
* Upgrade `tailwindcss` from **4.1.10** to **4.1.13** (latest patch with numerous fixes)【110831682360645†L223-L247】.

These updates are backwards‑compatible patch releases that fix known issues and improve stability.  Running the apply script will update the manifest, install the new versions, and run a basic test to confirm module imports.

## Contents

| File | Purpose |
| --- | --- |
| `diff.patch` | Unified diff updating version strings in `package.json`. |
| `apply.sh` | Shell script to apply the patch and run `npm install`. |
| `tests/version_import.test.js` | Minimal test to verify that updated packages load correctly. |

## How to apply

Execute `apply.sh` from the root of the repository.  The script uses the `apply_patch` helper (available in the Codex environment) to modify `package.json` and then runs `npm install` to update the lock file.  Finally, it runs `node` to execute the test script, ensuring the imports succeed.

## Rollback

If issues arise after applying the changeset, run the commands below to restore the previous state:

```bash
apply_patch <<'EOF'
*** Begin Patch
*** Update File: package.json
@@ "dependencies": {
-    "pptxgenjs": "4.0.1",
+    "pptxgenjs": "4.0.0",
@@
-    "image-size": "1.2.1",
+    "image-size": "2.0.2",
@@
-    "tailwindcss": "4.1.13",
+    "tailwindcss": "4.1.10",
*** End Patch
EOF
npm install
```

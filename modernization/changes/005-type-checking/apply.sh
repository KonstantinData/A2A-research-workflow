#!/bin/bash
set -euo pipefail
# Apply static type checking via JSDoc and TypeScript check mode.

# Add tsconfig.json enabling checkJs for JavaScript files.
apply_patch <<'PATCH'
*** Begin Patch
*** Add File: tsconfig.json
@@
{
  "compilerOptions": {
    "allowJs": true,
    "checkJs": true,
    "noEmit": true,
    "target": "ES2022",
    "moduleResolution": "node"
  },
  "include": ["**/*.js"]
}
*** End Patch
PATCH

# Ensure package.json has a scripts block with typecheck
apply_patch <<'PATCH'
*** Begin Patch
*** Update File: package.json
@@
   "scripts": {
     "lint": "eslint . --ext .js"
@@
   }
*** End Patch
PATCH || true

# Add the typecheck script alongside lint (or create scripts section if missing)
apply_patch <<'PATCH'
*** Begin Patch
*** Update File: package.json
@@ "scripts": {
     "lint": "eslint . --ext .js"
@@
     "lint": "eslint . --ext .js",
     "typecheck": "tsc -p tsconfig.json"
*** End Patch
PATCH || true

# Amend CI workflow to run type check if present
if [ -f .github/workflows/ci.yml ]; then
  apply_patch <<'PATCH'
*** Begin Patch
*** Update File: .github/workflows/ci.yml
@@
       - name: Run linter
         run: npm run lint
       - name: Run tests
         run: |
           npm test || true
           pytest -q || true
@@
       - name: Run linter
         run: npm run lint
       - name: Run type check
         run: npm run typecheck
       - name: Run tests
         run: |
           npm test || true
           pytest -q || true
*** End Patch
PATCH || true
fi

echo "Type checking configuration applied."
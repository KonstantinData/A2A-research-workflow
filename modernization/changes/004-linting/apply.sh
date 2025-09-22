#!/bin/bash
set -euo pipefail
# Apply linting and formatting configuration.

apply_patch <<'PATCH'
*** Begin Patch
*** Add File: .eslintrc.json
@@
{
  "env": {
    "browser": false,
    "node": true,
    "es2022": true
  },
  "extends": [
    "eslint:recommended",
    "plugin:prettier/recommended"
  ],
  "parserOptions": {
    "ecmaVersion": 2022,
    "sourceType": "module"
  },
  "rules": {
    "no-unused-vars": ["warn"],
    "no-console": "off"
  }
}
*** End Patch
PATCH

apply_patch <<'PATCH'
*** Begin Patch
*** Add File: .prettierrc
@@
{
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 80,
  "semi": true
}
*** End Patch
PATCH

# Update package.json with devDependencies and lint script
apply_patch <<'PATCH'
*** Begin Patch
*** Update File: package.json
@@
   "typescript": "5.8.3"
@@
   },
+  "devDependencies": {
+    "eslint": "^9.1.0",
+    "eslint-config-prettier": "^9.1.0",
+    "prettier": "^3.2.5"
+  },
+  "scripts": {
+    "lint": "eslint . --ext .js"
+  }
 }
*** End Patch
PATCH

# Amend CI workflow to run linting
if [ -f .github/workflows/ci.yml ]; then
  apply_patch <<'PATCH'
*** Begin Patch
*** Update File: .github/workflows/ci.yml
@@
       - name: Install Node dependencies
         run: npm install --legacy-peer-deps
@@
       - name: Run linter
         run: npm run lint
       - name: Run tests
*** End Patch
PATCH
fi

echo "Linting configuration applied."
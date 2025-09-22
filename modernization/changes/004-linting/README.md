# Changeset 004 – Linting and Formatting

This changeset adds ESLint and Prettier configuration to the repository.

* Introduces `.eslintrc.json` with recommended ESLint rules and Prettier integration.
* Adds `.prettierrc` specifying formatting preferences.
* Updates `package.json` to add `devDependencies` (`eslint`, `eslint-config-prettier`, `prettier`) and a `lint` script.
* Modifies the CI workflow to run `npm run lint` after installing dependencies.

Rollback: Remove `.eslintrc.json`, `.prettierrc`, the `lint` script and dev dependencies from `package.json`, and revert the CI workflow changes.
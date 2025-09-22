# Changeset 005 – Type checking

This changeset introduces static type checking using TypeScript in check mode.

* Adds `tsconfig.json` configured with `allowJs`, `checkJs`, and `noEmit`.
* Adds a `typecheck` script to `package.json` and integrates it into the CI workflow.
* Adds JSDoc annotations to functions in `answer.js` to improve type inference.
* The CI workflow now runs `npm run typecheck` to ensure type correctness.

Rollback: Remove `tsconfig.json`, remove the `typecheck` script from `package.json`, revert JSDoc additions if desired, and remove the type check step from the CI workflow.
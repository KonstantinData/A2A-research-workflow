# Modernization Backlog

This plan enumerates the work items required to modernize the repository and bring it into alignment with the target architecture.  Each entry references a corresponding finding from the diagnostics report and links to research notes and ADRs where available.  Items are prioritised roughly by severity and impact.

| Plan ID | Source (Finding) | Description | Changeset | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| **PLAN‑001** | FND‑001 (Outdated dependencies) | Upgrade `pptxgenjs` to v4.0.1, `image-size` to v1.2.1 and `tailwindcss` to v4.1.13 as per ADR‑0001.  Apply patch to `package.json`, regenerate `package‑lock.json` and ensure the project builds and tests pass. | `changes/001-update-deps` | Open | Patch-level update recommended by research【456086497610870†L229-L241】【110831682360645†L223-L247】. |
| **PLAN‑002** | FND‑003 (Missing CI/CD & security automation) | Establish a GitHub Actions workflow that installs dependencies, runs tests and linting, and builds the presentation.  Configure Dependabot for `npm` and `github-actions` ecosystems and enable CodeQL scanning. | `changes/002-ci-setup` | Open | Dependabot documentation notes that security updates automatically raise pull requests when enabled【560759686713697†L542-L556】. |
| **PLAN‑003** | FND‑004 (Lack of testing) | Introduce unit tests for JavaScript (e.g., using Jest) and Python (e.g., using pytest).  Target ≥80% coverage and ≥90% coverage on critical slide generation and image conversion code paths. | `changes/003-testing` | Open | Tests are essential to safely upgrade dependencies and refactor code【560759686713697†L572-L578】. |
| **PLAN‑004** | FND‑005 (No linting or formatting) | Integrate ESLint and Prettier with a standard style (e.g., Airbnb or Prettier defaults).  Enforce linting via CI. | `changes/004-linting` | Open | Improves readability and reduces bugs. |
| **PLAN‑005** | FND‑006 (No TypeScript types) | Migrate JavaScript files to TypeScript or add JSDoc type annotations.  Configure `tsconfig.json` and adjust build scripts accordingly. | `changes/005-type-checking` | Open | Static typing improves reliability and developer experience. |
| **PLAN‑006** | FND‑007 (External binary invocation) | Enhance `pptx_to_img.py` to validate input paths, check for LibreOffice availability, and optionally implement a pure‑Python conversion path (e.g., using `python-pptx` and `Pillow`). | `changes/006-harden-script` | Open | Reduces runtime failures and external dependencies. |
| **PLAN‑007** | FND‑008 (No containerization) | Provide a `Dockerfile` to build and run the project reproducibly, including Node and Python dependencies and LibreOffice for image conversion. | `changes/007-docker` | Open | Facilitates reproducible builds and integration with CI/CD. |
| **PLAN‑008** | FND‑009 (No observability/logging) | Integrate structured logging (e.g., `pino` for Node, `logging` for Python).  Include log levels and contextual metadata. | `changes/008-logging` | Open | Helps diagnose issues in production. |
| **PLAN‑009** | FND‑010 (Missing documentation) | Create technical documentation outlining project architecture, data flows, module responsibilities, and extension points.  Add diagrams and usage instructions. | `changes/009-docs` | Open | Essential for maintainability and onboarding. |

## Critical path

The modernization journey begins with **PLAN‑001** because outdated dependencies can introduce security and stability issues.  Once dependencies are up to date, **PLAN‑002** and **PLAN‑003** should be tackled in parallel: automated CI/CD ensures reliable builds and test suites provide safety nets for subsequent refactoring.  Remaining items focus on long‑term maintainability and developer experience.

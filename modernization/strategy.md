# Modernization Strategy

This document outlines the target architecture and migration strategy for the slide‑generation project.  It synthesizes the diagnostics findings, research notes and architecture decisions to create a coherent path from the current state to a secure, maintainable and production‑ready system.

## Target architecture

1. **Updated and maintained dependencies.**  All third‑party libraries are kept on current, supported versions.  Patch‑level updates are applied regularly to receive bug fixes and security patches.  For example, `pptxgenjs` will be updated to v4.0.1 (26 Jun 2025) to benefit from hyperlink and border fixes and the bundled upgrade of `image-size` to v1.2.1【456086497610870†L229-L241】.  `tailwindcss` will be updated to v4.1.13 (4 Sep 2025) to incorporate numerous CSS fixes and variant handling improvements【110831682360645†L223-L247】.

2. **Automated build, test and security pipelines.**  A CI workflow on GitHub Actions will install dependencies, run unit tests, lint and build the presentation on each pull request and commit to `main`.  Dependabot will automatically raise pull requests for vulnerable dependencies; when enabled, it will raise a pull request to update vulnerable GitHub Actions to the minimum patched version【560759686713697†L542-L556】.  CodeQL scanning will identify common vulnerability patterns.

3. **Comprehensive test suite.**  Introduce unit tests for both the JavaScript and Python components.  Tests will cover slide layout generation, image sizing functions, and the conversion pipeline.  Coverage goals are ≥80 % overall and ≥90 % on critical paths.  Automated tests are essential to validate dependency updates and refactorings【560759686713697†L572-L578】.

4. **Consistent coding standards.**  Adopt ESLint and Prettier to enforce a uniform code style across JavaScript and TypeScript files.  This reduces style‑related noise in code reviews and helps detect problematic patterns early.

5. **Type safety.**  Migrate JavaScript modules to TypeScript or augment them with JSDoc type annotations.  Static type checking reduces runtime errors and clarifies interfaces, easing collaboration and refactoring.

6. **Robust Python utilities.**  Enhance `pptx_to_img.py` to validate user‑supplied paths, verify that LibreOffice (`soffice`) is available before invocation, and handle errors gracefully.  Evaluate replacing the external conversion pipeline with a pure‑Python solution using `python‑pptx` and Pillow to improve portability.

7. **Containerized environment.**  Provide a Dockerfile that bundles Node.js, Python, required dependencies and LibreOffice.  A containerised build ensures reproducibility across environments and simplifies CI/CD integration.

8. **Structured logging and observability.**  Introduce logging in both JavaScript (e.g., using `pino`) and Python (using the built‑in `logging` module).  Logs should include contextual metadata (e.g., slide index, error messages) and support different log levels.

9. **Documentation and diagrams.**  Produce technical documentation under a `docs/` directory that explains the overall architecture, data flows (e.g., input data → slide generator → PowerPoint → image conversion), module responsibilities, and how to extend or customise the template.

## Migration strategy

The migration will proceed incrementally, following the backlog priority defined in `plan.md`:

1. **Dependency updates (PLAN‑001).**  Apply patch‑level upgrades and verify that the system still generates correct presentations and images.  This reduces the risk of known bugs without causing major disruptions.
2. **Build and security automation (PLAN‑002).**  Introduce a GitHub Actions workflow and Dependabot configuration.  This step can run in parallel with the next.
3. **Test suite development (PLAN‑003).**  Develop tests to cover the current functionality.  A stable test suite provides confidence for subsequent refactoring and type migration.
4. **Coding standards and type safety (PLAN‑004 & PLAN‑005).**  Add ESLint/Prettier and gradually refactor code to TypeScript or JSDoc types.
5. **Script hardening and containerisation (PLAN‑006 & PLAN‑007).**  Improve the robustness of the Python utilities and encapsulate the environment in a Docker image.  Ensure the container can build, test and run the application end‑to‑end.
6. **Observability and documentation (PLAN‑008 & PLAN‑009).**  Add structured logging and comprehensive documentation.  These tasks can be performed iteratively throughout the modernization process.

## Trade‑offs and assumptions

* **Balancing speed and safety.**  Patch‑level updates minimise risk, but any update can introduce subtle regressions.  Automated tests and CI mitigate this risk.
* **Incremental TypeScript adoption.**  Converting JavaScript to TypeScript may require refactoring and learning overhead.  Incremental adoption via JSDoc types allows gradual migration without blocking progress.
* **External binary dependency.**  LibreOffice provides high‑fidelity PPT→PDF conversion, but introduces a heavy dependency.  A pure‑Python alternative may sacrifice fidelity; this will be evaluated during PLAN‑006.

## References

* PptxGenJS release notes v4.0.1 detailing fixes and `image-size` upgrade【456086497610870†L229-L241】.
* Tailwind CSS release notes v4.1.13 summarising fixes and improvements【110831682360645†L223-L247】.
* GitHub Docs – Dependabot security updates automatically raise pull requests for vulnerable GitHub Actions【560759686713697†L542-L556】 and emphasise the importance of automated tests before merging updates【560759686713697†L572-L578】.

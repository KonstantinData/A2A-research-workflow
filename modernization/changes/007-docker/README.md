# Changeset 007 – Dockerization

This changeset introduces a multi‑stage `Dockerfile` enabling reproducible builds and runtime environments for the slide generator.

* The build stage (`node:20-bullseye`) installs Node.js, Python 3, LibreOffice, and all required dependencies.  It runs linting, type checking, and tests to ensure integrity.
* The runtime stage (`node:20-slim`) includes the application code, Python and LibreOffice, and runs `node answer.js` by default.
* A `.dockerignore` file excludes unnecessary files (node_modules, modernization directories, git history) from the build context.

Rollback: Delete the `Dockerfile` and `.dockerignore` files and remove any related CI configuration.
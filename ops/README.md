# Ops

## Purpose
Operational files for building, testing, and deploying the project.

## Files
- `Dockerfile`
- `docker-compose.yml`
- `Makefile`
- `CONFIG.md`
- `SECURITY.md`

## Dependencies
Docker and Make are required for the provided workflows.

## Usage
Use the Makefile targets or Docker configurations to containerize and run the workflow. When starting the services directly
with Docker Compose, build and launch the worker and API containers together:

```bash
docker-compose up --build worker api
```

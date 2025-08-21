
# Ops

## Purpose

Operational files for building, testing, and deploying the project.

## Files

- `Dockerfile`: Container definition for the core service.
- `docker-compose.yml`: Multi-service orchestration (e.g. backend + database).
- `Makefile`: Local automation for common tasks (build, lint, test, etc.).
- `CONFIG.md`: Documentation of environment variables and secrets.
- `SECURITY.md`: Notes on security practices and dependencies.

## Dependencies

- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)
- [Make](https://www.gnu.org/software/make/)

## Usage

Use the `Makefile` to run common tasks:

```bash
make lint      # Run linters
make test      # Run unit tests
make build     # Build Docker image
make run       # Run the service in Docker
```

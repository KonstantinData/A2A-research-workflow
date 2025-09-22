# Target Architecture & Strategy (Initial)
- Runtime: upgrade base image to Python 3.13 slim; keep 3.11 tested path for fallback.
- Dependencies: introduce `requirements.in` + pip-tools compiled lock with hashes; pin FastAPI/Uvicorn/WeasyPrint/OpenAI/Google APIs.
- Event-driven: single production entrypoint `app/app/worker.py`; all agents emit events; exports centralized in `output/*`.
- Observability: structured JSON logs with correlation, minimal metrics hook, health/readiness endpoints.
- CI/CD: add plan/research/ADR validation, SBOM + SCA scan, apply-dry-run.
- Security: allowlist for outbound email domains; secrets via env only; no inline secrets; reproducible artifact hashing for exports.

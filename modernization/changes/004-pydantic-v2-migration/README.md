# Batch 004 — Pydantic v2 Migration
Steps:
1. Update workflow API models to use Pydantic v2 config/validator patterns.
2. Add regression tests that exercise JSON schema and dataclass validation.
3. Record ADR and research notes enforcing v2-only support.
DoD:
- Unit tests covering request/response schemas pass.
- API models can validate domain events without v1 shims.

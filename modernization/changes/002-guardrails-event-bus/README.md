# Batch 002 — Guardrails
Deprecate legacy agents and enforce worker-only side effects.

DoD:
- Importing legacy modules raises RuntimeError.
- New CI test passes.

## Status: ✅ COMPLETED

The legacy agents have been successfully replaced with deprecation shims:
- `agents/autonomous_email_agent.py` - now raises RuntimeError
- `agents/autonomous_report_agent.py` - now raises RuntimeError  
- `agents/autonomous_research_agent.py` - now raises RuntimeError

All direct side effects have been eliminated. The system now uses the event-driven worker (`app/app/worker.py`) exclusively for email sending, PDF generation, and other external operations.

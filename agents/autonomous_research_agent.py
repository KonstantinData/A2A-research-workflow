raise RuntimeError(
    "Deprecated: Use the event-driven worker (app/app/worker.py). "
    "Agents must emit events; no direct exports/emails."
)

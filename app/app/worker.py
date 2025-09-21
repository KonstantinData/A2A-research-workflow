from __future__ import annotations
import asyncio, signal
from typing import Sequence, Optional
from app.core.orchestrator import Orchestrator
from app.core.event_store import EventStore, EventUpdate
from app.core.events import Event
from app.core.status import EventStatus
from app.core.logging import log_step
from app.core.policy.retry import default_backoff  # already exists
from app.integrations.mailer import EmailSender
from output.pdf_render import render_pdf
from output import csv_export

async def _handle_email_send_requested(ev: Event) -> None:
    payload = ev.payload or {}
    to = payload.get("to")
    subject = payload.get("subject") or "(no subject)"
    body = payload.get("body") or ""
    attachments: Optional[Sequence[str]] = payload.get("attachments")
    sender = EmailSender()
    msg_id = sender.send(
        to=to, subject=subject, body=body,
        attachments=attachments, event_id=ev.event_id, correlation_id=ev.correlation_id
    )
    log_step("orchestrator", "email_sent", {"event_id": ev.event_id, "message_id": msg_id})

async def _handle_report_ready(ev: Event) -> None:
    rows = (ev.payload or {}).get("rows") or []
    meta = (ev.payload or {}).get("meta") or {}
    pdf_path = render_pdf(rows, [], meta, None)
    csv_path = csv_export.export_csv(rows, None)
    EventStore.update(ev.event_id, EventUpdate(status=EventStatus.COMPLETED))
    log_step("orchestrator", "artifacts_written",
             {"event_id": ev.event_id, "pdf": str(pdf_path), "csv": str(csv_path)})

async def _main() -> None:
    handlers = {
        "EmailSendRequested": _handle_email_send_requested,
        "ReportReady": _handle_report_ready,
        # "UserReplyReceived" handled by Orchestrator fallback
    }
    orch = Orchestrator(handlers, store=EventStore, batch_size=25, max_attempts=5, backoff=default_backoff)
    stop = asyncio.Event()

    def _graceful(*_):
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _graceful)

    log_step("worker", "starting", {})

    stop_task = asyncio.create_task(stop.wait())
    orchestrator_task = asyncio.create_task(orch.start())

    try:
        done, _ = await asyncio.wait(
            {stop_task, orchestrator_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if stop_task in done:
            orch.stop()
            await orchestrator_task
        else:
            stop.set()
            await stop_task
            exc = orchestrator_task.exception()
            if exc is not None:
                raise exc
    finally:
        for task in (stop_task, orchestrator_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(stop_task, orchestrator_task, return_exceptions=True)

    log_step("worker", "stopped", {})

if __name__ == "__main__":
    asyncio.run(_main()) 

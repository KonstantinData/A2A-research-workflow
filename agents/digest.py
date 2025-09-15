import json

from config.settings import SETTINGS


def send_daily_admin_digest(to: str):
    p = SETTINGS.workflows_dir / "summary.json"
    if not p.exists(): 
        return
    s = json.loads(p.read_text(encoding="utf-8"))
    lines = [
        f"workflow_id: {s.get('workflow_id')}",
        f"errors: {s.get('errors')}  warnings: {s.get('warnings')}",
        f"reports_generated: {s.get('reports_generated')}  mails_sent: {s.get('mails_sent')}",
    ]
    ah = s.get("artifact_health") or {}
    lines += [
        f"pdf_ok: {ah.get('pdf_ok')}  pdf_size: {ah.get('pdf_size')}",
        f"csv_ok: {ah.get('csv_ok')}  csv_rows: {ah.get('csv_rows')}  empty_run: {ah.get('empty_run')}",
    ]
    body = "\n".join(lines)
    from integrations.email_sender import send_email
    send_email(to=to, subject="A2A daily digest", body=body)

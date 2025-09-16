import json
from email.message import EmailMessage

from integrations import email_reader


class _FakeIMAP:
    def __init__(self, raw_message: bytes, store_calls: list[tuple[bytes, str]]):
        self._raw = raw_message
        self._store_calls = store_calls

    def login(self, user: str, pwd: str) -> None:
        assert user == "user"
        assert pwd == "pass"

    def select(self, folder: str) -> None:
        assert folder == "INBOX"

    def search(self, charset, criteria):
        return "OK", [b"1"]

    def fetch(self, uid, query):
        return "OK", [(b"1 (RFC822 {len})", self._raw)]

    def store(self, uid, flags, value):
        self._store_calls.append((uid, value))

    def logout(self) -> None:
        pass


def test_fetch_replies_uses_headers_and_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_PORT", "993")
    monkeypatch.setenv("IMAP_USER", "user")
    monkeypatch.setenv("IMAP_PASS", "pass")

    monkeypatch.setattr(email_reader.SETTINGS, "workflows_dir", tmp_path)

    task_id = "123e4567-e89b-12d3-a456-426655440000"
    event_id = "2024-05-01_0900"
    outbound_id = f"<task-{task_id}@example.com>"
    email_reader.record_outbound_message(outbound_id, task_id=task_id, event_id=event_id)

    msg = EmailMessage()
    msg["Subject"] = 'Re: [Research Agent] Missing Information – "Quarterly Review"'
    msg["From"] = "colleague@example.com"
    msg["Message-ID"] = "<reply-1@example.com>"
    msg["In-Reply-To"] = outbound_id
    msg["References"] = outbound_id
    msg.set_content(
        "Company: Example GmbH\n"
        "Domain: example.com\n"
        "+49 12345678\n"
        "contact@example.com\n"
    )

    raw_bytes = msg.as_bytes()
    store_calls: list[tuple[bytes, str]] = []

    def _fake_imap_factory(host, port):
        assert host == "imap.example.com"
        assert port == 993
        return _FakeIMAP(raw_bytes, store_calls)

    monkeypatch.setattr(email_reader.imaplib, "IMAP4_SSL", _fake_imap_factory)

    first = email_reader.fetch_replies()
    assert len(first) == 1
    assert first[0]["task_id"] == task_id
    assert first[0]["fields"]["domain"] == "example.com"

    second = email_reader.fetch_replies()
    assert second == []

    assert len(store_calls) == 2

    state_path = tmp_path / "email_reader_state.json"
    assert state_path.exists()
    state = json.loads(state_path.read_text())
    assert "reply-1@example.com" in state["processed_message_ids"]

    outbound_key = outbound_id.strip("<>").lower()
    assert outbound_key in state["correlation_index"]
    assert state["correlation_index"][outbound_key]["task_id"] == task_id

    log_path = tmp_path / "email_reader.jsonl"
    contents = log_path.read_text().splitlines()
    assert any('"status": "reply_received"' in line for line in contents)
    assert any('"status": "reply_duplicate_skipped"' in line for line in contents)

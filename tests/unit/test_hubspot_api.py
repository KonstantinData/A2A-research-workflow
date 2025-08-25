import datetime as dt
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator, feature_flags
from integrations import hubspot_api


class DummyResp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests import HTTPError

            raise HTTPError("boom")

    def json(self):
        return self._data


def test_attach_pdf(monkeypatch, tmp_path):
    called = {}

    def fake_post(url, headers=None, files=None, data=None, timeout=10):
        called["post"] = True
        assert "files/v3/files" in url
        return DummyResp({"id": "file123"})

    def fake_put(url, headers=None, json=None, timeout=10):
        called["put"] = True
        assert "associations" in url
        return DummyResp({"id": "assoc456"})

    monkeypatch.setattr(hubspot_api.requests, "post", fake_post)
    monkeypatch.setattr(hubspot_api.requests, "put", fake_put)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "portal")

    pdf = tmp_path / "file.pdf"
    pdf.write_bytes(b"pdf")
    result = hubspot_api.attach_pdf(pdf, "123")
    assert called["post"] and called["put"]
    assert result == {"file_id": "file123", "association_id": "assoc456"}


def test_check_existing_report(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=30):
        captured["json"] = json
        return DummyResp({"results": [{"id": "1"}]})

    monkeypatch.setattr(hubspot_api.requests, "post", fake_post)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    result = hubspot_api.check_existing_report("123")
    assert result == {"id": "1"}
    assert captured["json"]["filters"][1]["value"] == "123"


def test_check_existing_report_error(monkeypatch):
    def fake_post(*a, **k):
        return DummyResp({}, status=403)

    monkeypatch.setattr(hubspot_api.requests, "post", fake_post)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    with pytest.raises(Exception):
        hubspot_api.check_existing_report("123")


def _run_base(monkeypatch, tmp_path, check_result):
    monkeypatch.setattr(feature_flags, "ATTACH_PDF_TO_HUBSPOT", True)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "portal")
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))

    called = {"attach": 0}

    def fake_attach(path: Path, cid: str) -> None:
        called["attach"] += 1

    def fake_pdf(data, path):
        path.write_text("pdf")

    def fake_csv(data, path):
        path.write_text("csv")

    def fake_upsert(data):
        return "123"

    orchestrator.run(
        triggers=[],
        researchers=[],
        consolidate_fn=lambda x: {},
        pdf_renderer=fake_pdf,
        csv_exporter=fake_csv,
        hubspot_upsert=fake_upsert,
        hubspot_attach=fake_attach,
        hubspot_check_existing=lambda cid: check_result,
        company_id=None,
    )
    return called["attach"]


def test_run_uploads_when_no_report(monkeypatch, tmp_path):
    assert _run_base(monkeypatch, tmp_path, None) == 1


def test_run_skips_recent_report(monkeypatch, tmp_path):
    recent = {"createdAt": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")}
    assert _run_base(monkeypatch, tmp_path, recent) == 0


def test_run_uploads_when_old_report(monkeypatch, tmp_path):
    old = {
        "createdAt": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8))
        .isoformat()
        .replace("+00:00", "Z")
    }
    assert _run_base(monkeypatch, tmp_path, old) == 1


def test_run_propagates_check_error(monkeypatch, tmp_path):
    def raise_err(cid):
        raise RuntimeError("boom")

    monkeypatch.setattr(feature_flags, "ATTACH_PDF_TO_HUBSPOT", True)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "portal")
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)

    def fake_pdf(data, path):
        path.write_text("pdf")

    def fake_csv(data, path):
        path.write_text("csv")

    def fake_upsert(data):
        return "123"

    with pytest.raises(RuntimeError):
        orchestrator.run(
            triggers=[],
            researchers=[],
            consolidate_fn=lambda x: {},
            pdf_renderer=fake_pdf,
            csv_exporter=fake_csv,
            hubspot_upsert=fake_upsert,
            hubspot_attach=lambda p, c: None,
            hubspot_check_existing=raise_err,
        )


def _run_no_upload(monkeypatch, tmp_path, upsert_return, pdf_write):
    monkeypatch.setattr(feature_flags, "ATTACH_PDF_TO_HUBSPOT", True)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "portal")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)

    called = {"attach": 0}

    def fake_attach(path: Path, cid: str) -> None:
        called["attach"] += 1

    def fake_pdf(data, path):
        if pdf_write:
            path.write_text("pdf")

    def fake_csv(data, path):
        path.write_text("csv")

    orchestrator.run(
        triggers=[],
        researchers=[],
        consolidate_fn=lambda x: {},
        pdf_renderer=fake_pdf,
        csv_exporter=fake_csv,
        hubspot_upsert=lambda data: upsert_return,
        hubspot_attach=fake_attach,
        hubspot_check_existing=lambda cid: None,
    )
    return called["attach"]


def test_run_no_upload_without_company_id(monkeypatch, tmp_path):
    assert _run_no_upload(monkeypatch, tmp_path, None, True) == 0


def test_run_no_upload_without_report(monkeypatch, tmp_path):
    assert _run_no_upload(monkeypatch, tmp_path, "123", False) == 0


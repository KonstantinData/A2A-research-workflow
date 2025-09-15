import datetime as dt
from pathlib import Path
import sys

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import orchestrator
from config.settings import SETTINGS
from integrations import hubspot_api


TRIGGER = {
    "source": "calendar",
    "creator": "alice@example.com",
    "recipient": "alice@example.com",
    "payload": {},
}


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


def test_request_with_retry_retries_transient_errors(monkeypatch):
    calls = {"count": 0}
    responses = [DummyResp({}, status=429), DummyResp({}, status=502), DummyResp({"ok": True})]

    def fake_request(method, url, **kwargs):
        idx = calls["count"]
        calls["count"] += 1
        return responses[idx]

    monkeypatch.setattr(hubspot_api.requests, "request", fake_request)
    monkeypatch.setattr(hubspot_api.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(hubspot_api.random, "uniform", lambda a, b: 0)

    resp = hubspot_api._request_with_retry("get", "http://example.com")
    assert calls["count"] == 3
    assert resp.status_code == 200


def test_request_with_retry_raises_after_max_attempts(monkeypatch):
    calls = {"count": 0}

    def fake_request(method, url, **kwargs):
        calls["count"] += 1
        raise requests.RequestException("boom")

    monkeypatch.setattr(hubspot_api.requests, "request", fake_request)
    monkeypatch.setattr(hubspot_api.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(hubspot_api.random, "uniform", lambda a, b: 0)

    with pytest.raises(requests.RequestException):
        hubspot_api._request_with_retry("get", "http://example.com")
    assert calls["count"] == 4


def test_attach_pdf(monkeypatch, tmp_path):
    called = {"upload": False, "assoc": False}

    def fake_request(method, url, **kwargs):
        if "files/v3/files" in url:
            called["upload"] = True
            return DummyResp({"id": "file123"})
        if "associations" in url:
            called["assoc"] = True
            return DummyResp({})
        raise AssertionError("Unexpected URL")

    monkeypatch.setattr(hubspot_api, "_request_with_retry", fake_request)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "token")

    pdf = tmp_path / "file.pdf"
    pdf.write_bytes(b"pdf")
    result = hubspot_api.attach_pdf(pdf, "123")
    assert called["upload"] and called["assoc"]
    assert result == {"file_id": "file123"}


def test_check_existing_report(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        return DummyResp({"results": [{"id": "1"}]})

    monkeypatch.setattr(hubspot_api, "_request_with_retry", fake_request)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    result = hubspot_api.check_existing_report("123")
    assert result == {"id": "1"}
    assert captured["json"]["filters"][1]["value"] == "123"


def test_check_existing_report_error(monkeypatch):
    def fake_request(*a, **k):
        return DummyResp({}, status=403)

    monkeypatch.setattr(hubspot_api, "_request_with_retry", fake_request)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    with pytest.raises(Exception):
        hubspot_api.check_existing_report("123")


def test_list_company_reports(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["url"] = url
        return DummyResp({"results": [{"id": "f1"}]})

    monkeypatch.setattr(hubspot_api, "_request_with_retry", fake_request)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    result = hubspot_api.list_company_reports("123")
    assert result == [{"id": "f1"}]
    assert "associations/files" in captured["url"]


def test_list_company_reports_error(monkeypatch):
    def fake_request(*a, **k):
        return DummyResp({}, status=500)

    monkeypatch.setattr(hubspot_api, "_request_with_retry", fake_request)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    with pytest.raises(RuntimeError):
        hubspot_api.list_company_reports("123")


def test_find_similar_companies(monkeypatch):
    captured = {}

    def fake_request(method, url, **kwargs):
        captured["json"] = kwargs["json"]
        data = {
            "results": [
                {
                    "properties": {
                        "name": "Acme",
                        "domain": "acme.com",
                        "industry_group": "Energy",
                        "industry": "Oil",
                        "description": "desc",
                    }
                }
            ]
        }
        return DummyResp(data)

    monkeypatch.setattr(hubspot_api, "_request_with_retry", fake_request)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    res = hubspot_api.find_similar_companies("Energy", "Oil", None)
    assert res[0]["company_name"] == "Acme"
    assert captured["json"]["filterGroups"][0]["filters"][0]["propertyName"] == "industry_group"


def test_find_similar_companies_error(monkeypatch):
    def fake_request(*a, **k):
        return DummyResp({}, status=400)

    monkeypatch.setattr(hubspot_api, "_request_with_retry", fake_request)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    with pytest.raises(RuntimeError):
        hubspot_api.find_similar_companies("Energy", "Oil", None)


def _run_base(monkeypatch, tmp_path, check_result, reply=None):
    monkeypatch.setattr(SETTINGS, "attach_pdf_to_hubspot", True)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    if reply is None:
        monkeypatch.setattr(orchestrator.email_reader, "fetch_replies", lambda: [])
    else:
        monkeypatch.setattr(
            orchestrator.email_reader,
            "fetch_replies",
            lambda: [{"creator": TRIGGER["creator"], "text": reply}],
        )

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
        triggers=[TRIGGER],
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


def test_run_prompts_and_continues(monkeypatch, tmp_path):
    existing = {"id": "r1"}
    assert _run_base(monkeypatch, tmp_path, existing, "Ja") == 1


def test_run_prompts_and_skips(monkeypatch, tmp_path):
    existing = {"id": "r1"}
    assert _run_base(monkeypatch, tmp_path, existing, "Nein") == 0


def test_run_propagates_check_error(monkeypatch, tmp_path):
    def raise_err(cid):
        raise RuntimeError("boom")

    monkeypatch.setattr(SETTINGS, "attach_pdf_to_hubspot", True)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)

    def fake_pdf(data, path):
        path.write_text("pdf")

    def fake_csv(data, path):
        path.write_text("csv")

    def fake_upsert(data):
        return "123"

    with pytest.raises(RuntimeError):
        orchestrator.run(
            triggers=[TRIGGER],
            researchers=[],
            consolidate_fn=lambda x: {},
            pdf_renderer=fake_pdf,
            csv_exporter=fake_csv,
            hubspot_upsert=fake_upsert,
            hubspot_attach=lambda p, c: None,
            hubspot_check_existing=raise_err,
        )


def _run_no_upload(monkeypatch, tmp_path, upsert_return, pdf_write):
    monkeypatch.setattr(SETTINGS, "attach_pdf_to_hubspot", True)
    monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("A2A_TEST_MODE", "1")
    monkeypatch.setattr(orchestrator.email_sender, "send_email", lambda *a, **k: None)
    monkeypatch.setattr(orchestrator.email_reader, "fetch_replies", lambda: [])

    called = {"attach": 0}

    def fake_attach(path: Path, cid: str) -> None:
        called["attach"] += 1

    def fake_pdf(data, path):
        if pdf_write:
            path.write_text("pdf")

    def fake_csv(data, path):
        path.write_text("csv")

    orchestrator.run(
        triggers=[TRIGGER],
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


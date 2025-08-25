from pathlib import Path

from integrations import hubspot_api


class DummyResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

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

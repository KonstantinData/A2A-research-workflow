"""Tests for custom error hierarchy."""

import importlib.util
import pathlib


spec = importlib.util.spec_from_file_location(
    "a2a_errors", pathlib.Path("logging/errors.py")
)
errors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(errors)


def test_hard_fail_creates_github_issue(monkeypatch):
    called = {}

    def fake_post(url, headers, json, timeout):  # noqa: D401 - simple stub
        called["url"] = url
        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"html_url": "https://github.com/example/repo/issues/1"}

        return Response()

    monkeypatch.setenv("GITHUB_REPOSITORY", "example/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setattr(errors.requests, "post", fake_post)

    err = errors.HardFailError("Boom")

    assert called["url"] == "https://api.github.com/repos/example/repo/issues"
    assert err.issue_url == "https://github.com/example/repo/issues/1"


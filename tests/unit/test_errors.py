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

    class FakeSession:
        def get(self, url, headers, params, timeout):
            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return []

            return Response()

        def post(self, url, headers, json, timeout):  # noqa: D401 - simple stub
            called["url"] = url
            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"html_url": "https://github.com/example/repo/issues/1"}

            return Response()

    monkeypatch.setenv("GITHUB_REPOSITORY", "example/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setattr(errors.requests, "Session", lambda: FakeSession())

    err = errors.HardFailError("Boom")

    assert called["url"] == "https://api.github.com/repos/example/repo/issues"
    assert err.issue_url == "https://github.com/example/repo/issues/1"


def test_issue_deduplicates_and_comments(monkeypatch):
    calls = {"get": 0, "post": []}

    class FakeSession:
        def get(self, url, headers, params, timeout):
            calls["get"] += 1
            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return [
                        {
                            "title": "Boom",
                            "html_url": "https://github.com/example/repo/issues/2",
                            "comments_url": "https://api.github.com/repos/example/repo/issues/2/comments",
                        }
                    ]

            return Response()

        def post(self, url, headers, json, timeout):  # noqa: D401 - simple stub
            calls["post"].append((url, json))
            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"html_url": "https://github.com/example/repo/issues/2"}

            return Response()

    monkeypatch.setenv("GITHUB_REPOSITORY", "example/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setattr(errors.requests, "Session", lambda: FakeSession())

    url = errors.create_github_issue("Boom", "desc", run_url="http://run")
    assert url == "https://github.com/example/repo/issues/2"
    assert calls["get"] == 1
    assert calls["post"][0][0] == "https://api.github.com/repos/example/repo/issues/2/comments"
    assert "Run URL: http://run" in calls["post"][0][1]["body"]


def test_issue_labels_applied(monkeypatch):
    posts = {}

    class FakeSession:
        def get(self, url, headers, params, timeout):
            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return []

            return Response()

        def post(self, url, headers, json, timeout):
            posts["payload"] = json
            class Response:
                def raise_for_status(self):
                    pass

                def json(self):
                    return {"html_url": "https://github.com/example/repo/issues/3"}

            return Response()

    monkeypatch.setenv("GITHUB_REPOSITORY", "example/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setattr(errors.requests, "Session", lambda: FakeSession())

    url = errors.create_github_issue(
        "Boom",
        "desc",
        labels=["calendar"],
        run_url="http://run",
    )
    assert url == "https://github.com/example/repo/issues/3"
    assert posts["payload"]["labels"] == ["calendar"]
    assert posts["payload"]["body"].endswith("Run URL: http://run")


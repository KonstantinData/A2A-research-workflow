"""Custom error definitions and helpers.

The workflow distinguishes between *soft* failures – errors that should be
surfaced but do not necessarily abort the entire run – and *hard* failures that
require human attention.  When a hard failure is instantiated an issue is
created on GitHub (if the necessary configuration is available).
"""

from __future__ import annotations

from typing import Optional, Iterable
import os

import requests


class A2AError(Exception):
    """Base error for A2A workflow."""


class SoftFailError(A2AError):
    """A recoverable error that should be logged but does not halt execution."""


class HardFailError(A2AError):
    """An unrecoverable error.

    On instantiation this error attempts to create a GitHub issue describing the
    problem.  Failure to create an issue should not mask the original error so
    all exceptions from the GitHub API are swallowed.
    """

    def __init__(
        self,
        message: str,
        *,
        title: Optional[str] = None,
        body: str = "",
        labels: Optional[Iterable[str]] = None,
        run_url: Optional[str] = None,
    ):
        super().__init__(message)
        self.issue_url = None
        try:
            self.issue_url = create_github_issue(
                title or message,
                body,
                labels=labels,
                run_url=run_url,
            )
        except Exception:
            # We deliberately ignore errors here – the original exception is more
            # important than the failure to file an issue.
            self.issue_url = None


def create_github_issue(
    title: str,
    body: str = "",
    *,
    repo: Optional[str] = None,
    token: Optional[str] = None,
    labels: Optional[Iterable[str]] = None,
    run_url: Optional[str] = None,
) -> Optional[str]:
    """Create a GitHub issue and return its URL.

    Parameters
    ----------
    title:
        Title of the issue.
    body:
        Body/description for the issue.
    repo:
        Target repository in ``owner/name`` form.  If omitted, the value of the
        ``GITHUB_REPOSITORY`` environment variable is used.
    token:
        Personal access token or GitHub App token.  If omitted the function reads
        ``GITHUB_TOKEN`` from the environment.
    labels:
        Optional iterable of labels to apply to the issue when created.
    run_url:
        URL for the workflow run – appended to the body or comment verbatim.

    The function returns the URL of the created issue or ``None`` if the issue
    could not be created (e.g. missing configuration).
    """

    repo = repo or os.getenv("GITHUB_REPOSITORY")
    token = token or os.getenv("GITHUB_TOKEN")
    if not repo or not token:
        return None

    base = f"https://api.github.com/repos/{repo}"
    issues_url = f"{base}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    session = requests.Session()

    # Check for an existing open issue with the same title to avoid duplicates.
    resp = session.get(
        issues_url,
        headers=headers,
        params={"state": "open", "per_page": 100},
        timeout=10,
    )
    resp.raise_for_status()
    for issue in resp.json() or []:
        if issue.get("title") == title:
            comment_body = body
            if run_url:
                comment_body = f"{comment_body}\n\nRun URL: {run_url}" if comment_body else f"Run URL: {run_url}"
            session.post(
                issue.get("comments_url"),
                headers=headers,
                json={"body": comment_body},
                timeout=10,
            )
            return issue.get("html_url")

    payload = {"title": title}
    if body:
        payload["body"] = body
    if run_url:
        payload["body"] = f"{payload.get('body', '')}\n\nRun URL: {run_url}".lstrip()
    if labels:
        payload["labels"] = list(labels)

    response = session.post(issues_url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    return response.json().get("html_url")


__all__ = [
    "A2AError",
    "SoftFailError",
    "HardFailError",
    "create_github_issue",
]


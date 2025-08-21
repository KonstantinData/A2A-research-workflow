"""Custom error definitions and helpers.

The workflow distinguishes between *soft* failures – errors that should be
surfaced but do not necessarily abort the entire run – and *hard* failures that
require human attention. When a hard failure is instantiated an issue is
created on GitHub (if the necessary configuration is available).
"""

from __future__ import annotations

from typing import Optional
import os
import requests


class A2AError(Exception):
    """Base error for A2A workflow."""


class SoftFailError(A2AError):
    """A recoverable error that should be logged but does not halt execution."""


class HardFailError(A2AError):
    """An unrecoverable error.

    On instantiation this error attempts to create a GitHub issue describing the
    problem. Failure to create an issue should not mask the original error so
    all exceptions from the GitHub API are swallowed.
    """

    def __init__(self, message: str, *, title: Optional[str] = None, body: str = ""):
        super().__init__(message)
        self.issue_url = None
        try:
            self.issue_url = create_github_issue(title or message, body)
        except Exception:
            self.issue_url = None


def create_github_issue(
    title: str,
    body: str = "",
    *,
    repo: Optional[str] = None,
    token: Optional[str] = None,
) -> Optional[str]:
    """Create a GitHub issue and return its URL.

    Parameters
    ----------
    title:
        Title of the issue.
    body:
        Body/description for the issue.
    repo:
        Target repository in ``owner/name`` form. If omitted, the value of the
        ``GITHUB_REPOSITORY`` environment variable is used.
    token:
        Personal access token or GitHub App token. If omitted the function reads
        ``GITHUB_TOKEN`` from the environment.

    Returns
    -------
    str or None:
        The URL of the created issue or None if creation failed.
    """
    repo = repo or os.getenv("GITHUB_REPOSITORY")
    token = token or os.getenv("GITHUB_TOKEN")
    if not repo or not token:
        return None

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {"title": title, "body": body}

    response = requests.post(url, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    return response.json().get("html_url")


__all__ = [
    "A2AError",
    "SoftFailError",
    "HardFailError",
    "create_github_issue",
]

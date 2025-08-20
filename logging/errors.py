"""Custom error definitions and GitHub issue helper."""

from __future__ import annotations

import os
from typing import Optional

import requests


class A2AError(Exception):
    """Base error for A2A workflow."""


class HardFailError(A2AError):
    """Error that creates a GitHub issue when instantiated."""

    def __init__(self, message: str) -> None:  # pragma: no cover - simple
        super().__init__(message)
        self.issue_url: Optional[str] = None

        repo = os.getenv("GITHUB_REPOSITORY")
        token = os.getenv("GITHUB_TOKEN")
        if not repo or not token:
            return

        url = f"https://api.github.com/repos/{repo}/issues"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
        payload = {"title": "A2A hard failure", "body": message}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        self.issue_url = response.json().get("html_url")


__all__ = ["A2AError", "HardFailError"]

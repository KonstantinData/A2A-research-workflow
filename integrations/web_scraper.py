"""Simple HTTP-based web scraper."""

from __future__ import annotations

import requests


def scrape(url: str, *, timeout: int = 10) -> str:
    """Fetch ``url`` and return the response body as text.

    The function performs a basic HTTP ``GET`` request and raises an exception on
    network errors or non-success status codes.  Only minimal scraping features
    are implemented – callers may parse the returned HTML as needed.
    """

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


__all__ = ["scrape"]

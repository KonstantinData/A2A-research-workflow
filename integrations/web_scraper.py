"""Simple HTTP-based web scraper."""

from __future__ import annotations

import requests

from core.utils import log_step


def scrape(url: str, *, timeout: int = 10) -> str:
    """Fetch ``url`` and return the response body as text.

    The function performs a basic HTTP ``GET`` request and raises an exception on
    network errors or non-success status codes.  Only minimal scraping features
    are implemented – callers may parse the returned HTML as needed.
    """

    headers = {'User-Agent': 'A2A-Research-Workflow/1.0'}
    try:
        resp = requests.get(url, timeout=timeout, headers=headers)
    except requests.RequestException as exc:
        log_step(
            "web_scraper",
            "request_failed",
            {"url": url, "error": str(exc)},
            severity="error",
        )
        raise
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        log_step(
            "web_scraper",
            "http_error",
            {"url": url, "status": resp.status_code, "error": str(exc)},
            severity="error",
        )
        raise
    text = resp.text
    log_step(
        "web_scraper",
        "scrape_ok",
        {
            "url": url,
            "status": resp.status_code,
            "content_length": len(text),
        },
    )
    return text


__all__ = ["scrape"]

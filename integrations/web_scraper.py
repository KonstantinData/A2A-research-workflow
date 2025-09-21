"""Simple HTTP-based web scraper."""

from __future__ import annotations

import time

import requests

from core.utils import log_step
from app.core.policy.retry import MAX_ATTEMPTS, backoff_seconds


def scrape(url: str, *, timeout: int = 10) -> str:
    """Fetch ``url`` and return the response body as text.

    The function performs a basic HTTP ``GET`` request and raises an exception on
    network errors or non-success status codes.  Only minimal scraping features
    are implemented – callers may parse the returned HTML as needed.
    """

    headers = {'User-Agent': 'A2A-Research-Workflow/1.0'}
    resp = None
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers)
            resp.raise_for_status()
            break
        except requests.HTTPError as exc:
            last_exc = exc
            if resp is not None and resp.status_code < 500:
                log_step(
                    "web_scraper",
                    "http_error",
                    {"url": url, "status": resp.status_code, "error": str(exc)},
                    severity="error",
                )
                raise
            if attempt >= MAX_ATTEMPTS:
                log_step(
                    "web_scraper",
                    "http_error",
                    {"url": url, "status": resp.status_code if resp else None, "error": str(exc)},
                    severity="error",
                )
                raise
            delay = backoff_seconds(attempt)
            log_step(
                "web_scraper",
                "request_retry",
                {
                    "url": url,
                    "attempt": attempt,
                    "status": resp.status_code if resp else None,
                    "backoff_seconds": round(delay, 2),
                },
                severity="warning",
            )
            time.sleep(delay)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= MAX_ATTEMPTS:
                log_step(
                    "web_scraper",
                    "request_failed",
                    {"url": url, "error": str(exc)},
                    severity="error",
                )
                raise
            delay = backoff_seconds(attempt)
            log_step(
                "web_scraper",
                "request_retry",
                {
                    "url": url,
                    "attempt": attempt,
                    "error": str(exc),
                    "backoff_seconds": round(delay, 2),
                },
                severity="warning",
            )
            time.sleep(delay)
    if resp is None:
        if last_exc:
            raise last_exc
        raise RuntimeError("web_scraper request failed")
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

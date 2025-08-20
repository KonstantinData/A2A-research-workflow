"""Duplicate detection helpers.

The real system would query HubSpot to determine whether a company already
exists.  For testing purposes we implement a small in-memory duplicate checker
that scores a candidate against an existing record using a hybrid of domain and
company name similarity.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Dict
from urllib.parse import urlparse


def _normalize_domain(domain: str) -> str:
    """Return the effective second level domain of ``domain``.

    The function strips protocols and leading ``www`` and lowercases the
    resulting host name.
    """

    if not domain:
        return ""
    parsed = urlparse(domain if "://" in domain else f"http://{domain}")
    host = parsed.netloc or parsed.path
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _name_similarity(a: str, b: str) -> float:
    """Approximate string similarity using :mod:`difflib`.

    ``SequenceMatcher`` provides a ratio between 0 and 1 which we treat as a
    rough substitute for a more advanced Jaro‑Winkler score.
    """

    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def hybrid_score(existing: Dict[str, str], candidate: Dict[str, str]) -> float:
    """Calculate a duplicate score for ``candidate`` against ``existing``.

    The score is based on domain equality (60%) and fuzzy name similarity
    (40%).  A perfect match yields ``1.0``.
    """

    domain_score = 0.0
    if _normalize_domain(existing.get("domain")) == _normalize_domain(
        candidate.get("domain")
    ):
        domain_score = 1.0

    name_score = _name_similarity(
        existing.get("legal_name", ""), candidate.get("legal_name", "")
    )

    return 0.6 * domain_score + 0.4 * name_score


def is_duplicate(existing: Dict[str, str], candidate: Dict[str, str], *, threshold: float = 0.8) -> bool:
    """Return ``True`` if ``candidate`` is considered a duplicate of ``existing``.

    Parameters
    ----------
    existing, candidate:
        Mappings containing at least ``domain`` and ``legal_name``.
    threshold:
        Minimum score to be classified as a duplicate.
    """

    return hybrid_score(existing, candidate) >= threshold


__all__ = ["hybrid_score", "is_duplicate"]


"""Tests for consolidate utilities."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

try:  # pragma: no cover - guard legacy consolidate module
    from core.consolidate import consolidate
except ImportError:  # pragma: no cover - module removed
    pytestmark = pytest.mark.skip(
        reason="Legacy consolidate removed; functionality migrated"
    )


def test_consolidate_merges_and_annotations():
    results = [
        {
            "source": "agent1",
            "payload": {"summary": "We develop software products."},
        },
        {
            "source": "agent2",
            "payload": {"companies": ["A", "B"]},
        },
    ]

    combined = consolidate(results)

    assert combined["summary"] == "We develop software products."
    assert combined["companies"] == ["A", "B"]
    assert combined["meta"]["summary"]["source"] == "agent1"
    assert "last_verified_at" in combined["meta"]["summary"]
    assert "62.01" in combined["classification"]["wz2008"]

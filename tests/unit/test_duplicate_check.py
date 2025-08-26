"""Tests for duplicate detection."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.duplicate_check import is_duplicate


def test_is_duplicate_detects_similarity():
    record = {"name": "Acme GmbH"}
    existing = [{"name": "ACME gmbh"}]
    assert is_duplicate(record, existing) is True


def test_is_duplicate_rejects_different_names():
    record = {"name": "Acme"}
    existing = [{"name": "Different"}]
    assert is_duplicate(record, existing) is False

"""Tests for duplicate detection."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.duplicate_check import is_duplicate


def test_is_duplicate_always_false():
    record = {"name": "Acme"}
    assert is_duplicate(record) is False

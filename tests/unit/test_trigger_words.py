"""Tests for trigger word utilities."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.trigger_words import contains_trigger


def test_contains_trigger():
    words = {"research", "meeting"}
    assert contains_trigger("Research meeting", words)
    assert not contains_trigger("no match", words)
    assert contains_trigger(" research ", words)
    assert not contains_trigger("", words)

"""Tests for translation utilities."""

from core.translate import to_us_business_english


def test_translation_noop_without_api():
    text = "Forschungsmeeting"
    assert to_us_business_english(text) == text

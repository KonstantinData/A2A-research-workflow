"""Tests for classification utilities."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.classify import classify


def test_classify_basic():
    data = {
        "description": "We offer software consulting and retail services.",
        "gpt_tags": ["AI", "SaaS"],
    }
    result = classify(data)
    assert "62.01" in result["wz2008"]  # software
    assert "70.22" in result["wz2008"]  # consulting
    assert "47.19" in result["wz2008"]  # retail
    # GPT tags merged with keyword tags
    assert "AI" in result["gpt_tags"]
    assert "software" in result["gpt_tags"]

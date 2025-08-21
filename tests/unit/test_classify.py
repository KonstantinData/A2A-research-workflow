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
    # Codes returned for all supported classification systems
    for code in ("62.01", "70.22", "47.19"):
        assert code in result["nace"]
        assert code in result["wz2008"]
        assert code in result["onace"]
        assert code in result["noga"]
    # Labels stored for each scheme
    assert result["labels"]["wz2008"]["62.01"].startswith("Erbringung")
    # GPT tags merged with keyword tags
    assert "AI" in result["gpt_tags"]
    assert "software" in result["gpt_tags"]

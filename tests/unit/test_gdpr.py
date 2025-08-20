"""Tests for GDPR anonymisation helpers."""

from compliance import gdpr


def test_anonymize_removes_common_pii():
    data = {
        "name": "John Doe",
        "email": "john@example.com",
        "info": {
            "phone": "+1-202-555-0143",
            "note": "Reach me at john@example.com",
        },
    }

    result = gdpr.anonymize(data)

    # Top-level keys should be removed entirely
    assert "name" not in result
    assert "email" not in result

    # Nested keys should also be removed and text should be redacted
    assert "phone" not in result["info"]
    assert result["info"]["note"] == "Reach me at <redacted>"


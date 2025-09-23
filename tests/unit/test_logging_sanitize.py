import json
import logging

from a2a_logging.logger import JSONFormatter
from a2a_logging.sanitize import sanitize_message


def _formatted_message(message: str) -> str:
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    payload = json.loads(formatted)
    return payload["message"]


def test_formatter_sanitizes_email() -> None:
    message = "Contact us at user@example.com for details."
    formatted = _formatted_message(message)

    assert "user@example.com" not in formatted
    assert formatted == sanitize_message(message)


def test_formatter_sanitizes_phone_number() -> None:
    message = "Call +1 (555) 123-4567 to reach support."
    formatted = _formatted_message(message)

    assert "+1 (555) 123-4567" not in formatted
    assert formatted == sanitize_message(message)


def test_formatter_leaves_non_pii_untouched() -> None:
    message = "No sensitive information here."
    formatted = _formatted_message(message)

    assert formatted == message

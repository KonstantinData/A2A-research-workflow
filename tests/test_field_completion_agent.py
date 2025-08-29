import json
from typing import Any, Dict

import pytest

from agents import field_completion_agent


def _make_trig(summary: str) -> Dict[str, Any]:
    return {"payload": {"summary": summary}}


def test_openai_result_preserved(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    class FakeOpenAI:
        class ChatCompletion:
            @staticmethod
            def create(*args, **kwargs):
                return {
                    "choices": [
                        {"message": {"content": json.dumps({"company_name": "ACME Inc", "domain": "acme.com"})}}
                    ]
                }

    monkeypatch.setattr(field_completion_agent, "openai", FakeOpenAI)

    trig = _make_trig("Other GmbH https://other.org")
    result = field_completion_agent.run(trig)
    assert result == {"company_name": "ACME Inc", "domain": "acme.com"}


def test_parser_fallback_on_openai_failure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    class FakeOpenAI:
        class ChatCompletion:
            @staticmethod
            def create(*args, **kwargs):
                raise RuntimeError("fail")

    monkeypatch.setattr(field_completion_agent, "openai", FakeOpenAI)

    trig = _make_trig("Meeting with MegaCorp GmbH at https://MegaCorp.com/about")
    result = field_completion_agent.run(trig)
    assert result == {"company_name": "MegaCorp GmbH", "domain": "megacorp.com"}


def test_returns_empty_when_nothing_found(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    class FakeOpenAI:
        class ChatCompletion:
            @staticmethod
            def create(*args, **kwargs):
                raise RuntimeError("fail")

    monkeypatch.setattr(field_completion_agent, "openai", FakeOpenAI)

    trig = _make_trig("meeting with unknown person")
    result = field_completion_agent.run(trig)
    assert result == {}

"""Tests for structured JSON logger."""

import json
import importlib.util
import pathlib
import logging


spec = importlib.util.spec_from_file_location(
    "a2a_logger", pathlib.Path("logging/logger.py")
)
logger_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(logger_module)


def test_logger_emits_json_with_context(capfd):
    logger = logger_module.get_logger(run_id="run123", stage="unit")
    logger.info("hello world")

    out, _ = capfd.readouterr()
    payload = json.loads(out.strip())

    assert payload["run_id"] == "run123"
    assert payload["stage"] == "unit"
    assert payload["level"] == "info"
    assert payload["message"] == "hello world"


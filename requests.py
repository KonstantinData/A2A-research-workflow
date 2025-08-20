"""Minimal requests stub used in tests."""

def post(url, headers=None, json=None, timeout=10):  # pragma: no cover - simple stub
    raise RuntimeError("network disabled")

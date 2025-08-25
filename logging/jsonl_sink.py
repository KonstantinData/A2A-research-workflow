"""Append-only JSONL sink utility."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def append(path: Path, record: Dict[str, Any]) -> None:
    """Append a JSON record to ``path`` as a JSONL line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

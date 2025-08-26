# output/pdf_render.py
"""PDF rendering using WeasyPrint if available, with graceful fallback."""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def _html_from_data(data: Any) -> str:
    return f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>A2A Report</title></head>
<body>
<h1>A2A Research Report</h1>
<pre>{json.dumps(data, indent=2, ensure_ascii=False)}</pre>
</body></html>"""


def render_pdf(data: Any, out_path: Path) -> None:
    html = _html_from_data(data)
    try:
        from weasyprint import HTML  # type: ignore

        HTML(string=html).write_pdf(str(out_path))
    except Exception:
        # Fallback: write HTML alongside with .pdf extension for environments without WeasyPrint
        out_path.write_text(html, encoding="utf-8")

# output/pdf_render.py
"""PDF rendering helpers.

This module provides a small wrapper around WeasyPrint (when available) and a
fallback implementation for environments without the dependency.  To remain
compatible with legacy tests the exposed :func:`render_pdf` function accepts two
different calling conventions:

``render_pdf(mapping, path)``
    Serialises ``mapping`` to HTML and writes the result to ``path``.  This is
    the behaviour that existed before this change and is still used by several
    integration tests.

``render_pdf(rows, fields, meta=None)``
    New behaviour used by export safety tests.  The report is written to
    ``output/exports/report.pdf`` and if ``rows`` is empty a placeholder PDF is
    generated explaining why no data is available.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List
import json


def _html_from_data(data: Any) -> str:
    """Return a very small HTML document representing ``data``."""

    return (
        "<!doctype html>\n"
        "<html>\n<head><meta charset=\"utf-8\"><title>A2A Report</title></head>\n"
        "<body>\n<h1>A2A Research Report</h1>\n"
        f"<pre>{json.dumps(data, indent=2, ensure_ascii=False)}</pre>\n"
        "</body></html>"
    )


def _write_placeholder_pdf(out_path: Path, reason: str | None) -> None:
    """Create a tiny PDF file stating that no data was available."""

    try:
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore

        c = canvas.Canvas(str(out_path), pagesize=A4)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, 750, "No data to report")
        c.setFont("Helvetica", 10)
        c.drawString(100, 730, f"Reason: {reason or 'No valid triggers'}")
        c.save()
        return
    except Exception:
        # Dependency not available – fall back to a plain text file with .pdf
        # extension.  While not a valid PDF it still clearly communicates the
        # issue and keeps tests independent from external libraries.
        out_path.write_text(
            f"No data to report. Reason: {reason or 'No valid triggers'}",
            encoding="utf-8",
        )


def render_pdf(
    data_or_rows: Any,
    out_path_or_fields: Any,
    meta: Dict[str, Any] | None = None,
) -> None:
    """Render a PDF report.

    Parameters
    ----------
    data_or_rows:
        Mapping of data (legacy mode) or iterable of row dictionaries.
    out_path_or_fields:
        Target path (legacy) or iterable of field names (new mode).
    meta:
        Optional metadata used in new mode to provide a reason for empty
        exports.
    """

    # --- Legacy behaviour: render_pdf(data, out_path) -------------------
    if isinstance(out_path_or_fields, (str, Path)):
        out_path = Path(out_path_or_fields)
        html = _html_from_data(data_or_rows)
        try:
            from weasyprint import HTML  # type: ignore

            HTML(string=html).write_pdf(str(out_path))
        except Exception:
            out_path.write_text(html, encoding="utf-8")
        return

    # --- New behaviour: render_pdf(rows, fields, meta) -------------------
    rows: List[Dict[str, Any]] = list(data_or_rows or [])
    fields: List[str] = list(out_path_or_fields or [])  # retained for future use

    out_dir = Path("output/exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "report.pdf"

    if not rows:
        reason = (meta or {}).get("reason") if meta else None
        _write_placeholder_pdf(out_path, reason)
        return

    data = {"rows": rows, "fields": fields, "meta": meta or {}}
    html = _html_from_data(data)
    try:
        from weasyprint import HTML  # type: ignore

        HTML(string=html).write_pdf(str(out_path))
    except Exception:
        out_path.write_text(html, encoding="utf-8")


__all__ = ["render_pdf"]


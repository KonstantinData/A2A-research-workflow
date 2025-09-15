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
    ``output/exports/report.pdf`` and if ``rows`` is empty an empty PDF is
    generated explaining why no data is available.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from config.settings import SETTINGS

try:
    from weasyprint import HTML  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    HTML = None  # type: ignore

try:  # jinja2 is optional and may not be installed
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except Exception:  # pragma: no cover - fallback when dependency missing
    Environment = FileSystemLoader = select_autoescape = None  # type: ignore


def _ensure_weasyprint() -> None:
    """Verify that the WeasyPrint dependency is installed."""

    if HTML is None:
        raise RuntimeError(
            "WeasyPrint is required for PDF rendering. Install with 'pip install weasyprint'."
        )


def _html_from_data(data: Dict[str, Any]) -> str:
    """Return an HTML document representing ``data``.

    If a Jinja2 template is available a styled report is rendered.  Otherwise a
    minimal inline HTML table is produced.
    """

    tpl_dir = Path(__file__).resolve().parents[0] / "templates" / "pdf"
    tpl = tpl_dir / "report.html.j2"
    if Environment and tpl.exists():
        env = Environment(
            loader=FileSystemLoader(str(tpl_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            enable_async=False,
        )
        return env.get_template("report.html.j2").render(**data)

    # fallback: minimal inline HTML
    rows = data.get("rows") or []
    fields = data.get("fields") or []
    meta = data.get("meta") or {}
    items = "".join(
        "<tr>" + "".join(f"<td>{r.get(f, '')}</td>" for f in fields) + "</tr>"
        for r in rows
    )
    head = "".join(f"<th>{f}</th>" for f in fields)
    return (
        "<html><body><h1>Company Dossier</h1>"
        "<table><thead><tr>"
        f"{head}"
        "</tr></thead><tbody>"
        f"{items}"
        "</tbody></table>"
        f"<pre>{meta}</pre>"
        "</body></html>"
    )


def _write_empty_pdf(out_path: Path, reason: str | None) -> None:
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


def _write_html_pdf(html: str, out_path: Path) -> None:
    if HTML is None:
        if os.getenv("LIVE_MODE", "1") == "1":
            raise RuntimeError("WeasyPrint not available in LIVE mode")
        raise RuntimeError("WeasyPrint not available")
    HTML(string=html).write_pdf(str(out_path))


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

    live_mode = os.getenv("LIVE_MODE", "1") == "1"

    if live_mode:
        _ensure_weasyprint()

    # --- Legacy behaviour: render_pdf(data, out_path) -------------------
    if isinstance(out_path_or_fields, (str, Path)):
        out_path = Path(out_path_or_fields)
        html = _html_from_data(data_or_rows)
        try:
            _write_html_pdf(html, out_path)
        except Exception:
            if live_mode:
                raise
            out_path.write_text(html, encoding="utf-8")
        return

    # --- New behaviour: render_pdf(rows, fields, meta) -------------------
    rows: List[Dict[str, Any]] = list(data_or_rows or [])
    fields: List[str] = list(out_path_or_fields or [])  # retained for future use

    out_dir = SETTINGS.exports_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "report.pdf"

    if not rows:
        # Render ein Minimal-HTML mit WeasyPrint (wenn vorhanden); nur wenn weder
        # WeasyPrint noch ReportLab verfügbar sind, auf Text ausweichen.
        reason = (meta or {}).get("reason") if meta else None
        empty = {
            "fields": ["info"],
            "rows": [
                {
                    "info": f"No data to report. Reason: {reason or 'No valid triggers'}",
                }
            ],
            "meta": meta or {},
        }
        html = _html_from_data(empty)
        try:
            _write_html_pdf(html, out_path)
            return
        except Exception:
            if live_mode:
                raise
            try:
                _write_empty_pdf(out_path, reason)
                return
            except Exception:
                out_path.write_text(html, encoding="utf-8")
                return

    data = {"rows": rows, "fields": fields, "meta": meta or {}}
    html = _html_from_data(data)
    try:
        _write_html_pdf(html, out_path)
    except Exception:
        if live_mode:
            raise
        out_path.write_text(html, encoding="utf-8")


__all__ = ["render_pdf"]


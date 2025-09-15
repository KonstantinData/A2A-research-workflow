# output/pdf_render.py
"""PDF rendering helpers.

The public :func:`render_pdf` helper renders tabular PDF reports from an
iterable of row dictionaries.  It writes the PDF to ``out_path`` (or the
default exports directory) and returns the resulting :class:`~pathlib.Path`.
For legacy call sites that still provide a mapping and output path a
compatibility wrapper :func:`render_pdf_from_mapping` is available.  The
wrapper emits a :class:`DeprecationWarning` to encourage migration to the
unified API.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any, Dict, List, Mapping

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
    rows: list[dict[str, Any]],
    fields: list[str],
    meta: dict[str, Any] | None = None,
    out_path: Path | None = None,
) -> Path:
    """Render ``rows`` into a PDF table and return the written path."""

    live_mode = os.getenv("LIVE_MODE", "1") == "1"

    if live_mode:
        _ensure_weasyprint()

    normalized_rows: List[Dict[str, Any]] = list(rows or [])
    normalized_fields: List[str] = list(fields or [])
    normalized_meta: Dict[str, Any] = dict(meta or {})

    destination = Path(out_path) if out_path else SETTINGS.exports_dir / "report.pdf"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if not normalized_rows:
        reason = normalized_meta.get("reason")
        empty_payload = {
            "fields": ["info"],
            "rows": [
                {
                    "info": f"No data to report. Reason: {reason or 'No valid triggers'}",
                }
            ],
            "meta": normalized_meta,
        }
        html = _html_from_data(empty_payload)
        try:
            _write_html_pdf(html, destination)
        except Exception:
            if live_mode:
                raise
            try:
                _write_empty_pdf(destination, reason)
            except Exception:
                destination.write_text(html, encoding="utf-8")
        return destination

    data = {"rows": normalized_rows, "fields": normalized_fields, "meta": normalized_meta}
    html = _html_from_data(data)
    try:
        _write_html_pdf(html, destination)
    except Exception:
        if live_mode:
            raise
        destination.write_text(html, encoding="utf-8")
    return destination


def render_pdf_from_mapping(data: Mapping[str, Any], out_path: Path | str) -> Path:
    """Compatibility wrapper for the deprecated ``render_pdf(mapping, path)`` API."""

    warnings.warn(
        "render_pdf(mapping, path) is deprecated; call render_pdf(rows, fields, meta, out_path) instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    rows = list(data.get("rows") or [])  # type: ignore[arg-type]
    fields = list(data.get("fields") or [])  # type: ignore[arg-type]
    meta = data.get("meta")
    normalized_meta: Dict[str, Any] | None
    if isinstance(meta, Mapping):
        normalized_meta = dict(meta)
    else:
        normalized_meta = None
    return render_pdf(rows, fields, normalized_meta, Path(out_path))


__all__ = ["render_pdf"]


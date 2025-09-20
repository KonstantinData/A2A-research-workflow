from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from config.settings import SETTINGS


PdfRenderer = Callable[[List[Dict[str, Any]], List[str], Dict[str, Any] | None, Path | None], Path]
CsvExporter = Callable[[List[Dict[str, Any]], Path], None]


def resolve_exporters(
    pdf_renderer: PdfRenderer | None,
    csv_exporter: CsvExporter | None,
    *,
    test_mode: bool,
) -> Tuple[PdfRenderer, CsvExporter, PdfRenderer, CsvExporter]:
    from output import csv_export as csv_module
    from output import pdf_render as pdf_module

    fallback_pdf = pdf_module.render_pdf
    fallback_csv = csv_module.export_csv

    if not test_mode:
        return fallback_pdf, fallback_csv, fallback_pdf, fallback_csv

    return (
        pdf_renderer or fallback_pdf,
        csv_exporter or fallback_csv,
        fallback_pdf,
        fallback_csv,
    )


def create_idle_artifacts(
    *,
    log_event: Callable[[Dict[str, Any]], None],
) -> Tuple[Path, Path]:
    from output import csv_export
    from output import pdf_render

    outdir = SETTINGS.exports_dir
    outdir.mkdir(parents=True, exist_ok=True)

    pdf_path = outdir / "report.pdf"
    csv_path = outdir / "data.csv"

    try:
        pdf_render.render_pdf(
            [{"info": "No valid triggers in current window"}],
            ["info"],
            {"reason": "no_triggers"},
            pdf_path,
        )
        log_event({"status": "artifact_pdf", "path": str(pdf_path)})
    except Exception as exc:
        from core.utils import log_step
        log_step("exports", "artifact_pdf_error", 
                {"error": str(exc)}, severity="warning")

    try:
        csv_export.export_csv([], csv_path)
        log_event({"status": "artifact_csv", "path": str(csv_path)})
    except Exception as exc:
        from core.utils import log_step
        log_step("exports", "artifact_csv_error", 
                {"error": str(exc)}, severity="warning")

    return pdf_path, csv_path


def export_report(
    consolidated: Dict[str, Any],
    first_event_id: Any,
    pdf_renderer: PdfRenderer,
    csv_exporter: CsvExporter,
    fallback_pdf: PdfRenderer,
    fallback_csv: CsvExporter,
    *,
    log_event: Callable[[Dict[str, Any]], None],
    log_step: Callable[[str, str, Dict[str, Any]], None],
) -> Tuple[Path, Path]:
    outdir = SETTINGS.exports_dir
    outdir.mkdir(parents=True, exist_ok=True)

    pdf_path = outdir / "report.pdf"
    csv_path = outdir / "data.csv"

    # Convert flat consolidated dict to rows/fields format
    if "rows" in consolidated and "fields" in consolidated:
        # Already structured format
        rows = list(consolidated.get("rows") or [])
        fields = list(consolidated.get("fields") or [])
    else:
        # Flat format - convert to single row
        meta = consolidated.get("meta", {})
        # Exclude meta from the data row
        data_row = {k: v for k, v in consolidated.items() if k != "meta"}
        rows = [data_row] if data_row else []
        fields = list(data_row.keys()) if data_row else []
    
    meta_dict = dict(consolidated.get("meta", {})) if isinstance(consolidated.get("meta"), dict) else None

    rendered_pdf_path = pdf_renderer(rows, fields, meta_dict, pdf_path)
    if rendered_pdf_path:
        pdf_path = Path(rendered_pdf_path)

    if not isinstance(pdf_path, Path):
        raise TypeError("pdf_renderer must return a pathlib.Path or None")
    csv_exporter(rows, csv_path)

    try:
        if pdf_path.exists() and pdf_path.stat().st_size < 1000:
            fallback_pdf(
                [{"info": "invalid_artifact_detected"}],
                ["info"],
                {"reason": "invalid_artifact_detected"},
                pdf_path,
            )
        if csv_path.exists() and csv_path.stat().st_size < 50:  # Account for header row
            fallback_csv([], csv_path)
    except Exception as exc:
        from core.utils import log_step
        log_step("exports", "fallback_artifact_error", 
                {"error": str(exc)}, severity="warning")

    log_event({"event_id": first_event_id, "status": "artifact_pdf", "path": str(pdf_path)})
    log_event({"event_id": first_event_id, "status": "artifact_csv", "path": str(csv_path)})
    log_step(
        "orchestrator",
        "report_generated",
        {"event_id": first_event_id, "path": str(pdf_path)},
    )

    return pdf_path, csv_path


__all__ = [
    "resolve_exporters",
    "create_idle_artifacts",
    "export_report",
]

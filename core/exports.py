from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from config.settings import SETTINGS


PdfRenderer = Callable[[List[Dict[str, Any]], List[str], Dict[str, Any] | None, Path | None], Path]
CsvExporter = Callable[[List[Dict[str, Any]], Path], None]
JsonExporter = Callable[[List[Dict[str, Any]], Path | None], Path]


def resolve_exporters(
    pdf_renderer: PdfRenderer | None,
    csv_exporter: CsvExporter | None,
    json_exporter: JsonExporter | None = None,
    *,
    test_mode: bool,
) -> Tuple[PdfRenderer, CsvExporter, JsonExporter, PdfRenderer, CsvExporter, JsonExporter]:
    from output import csv_export as csv_module
    from output import pdf_render as pdf_module
    from output import json_export as json_module

    fallback_pdf = pdf_module.render_pdf
    fallback_csv = csv_module.export_csv
    fallback_json = json_module.export_json

    if not test_mode:
        return fallback_pdf, fallback_csv, fallback_json, fallback_pdf, fallback_csv, fallback_json

    return (
        pdf_renderer or fallback_pdf,
        csv_exporter or fallback_csv,
        json_exporter or fallback_json,
        fallback_pdf,
        fallback_csv,
        fallback_json,
    )


def create_idle_artifacts(
    *,
    log_event: Callable[[Dict[str, Any]], None],
) -> Tuple[Path, Path, Path]:
    from output import csv_export
    from output import pdf_render
    from output import json_export

    outdir = SETTINGS.exports_dir
    outdir.mkdir(parents=True, exist_ok=True)

    pdf_path = outdir / "report.pdf"
    csv_path = outdir / "data.csv"
    json_path = outdir / "data.json"

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

    try:
        json_export.export_json([], json_path)
        log_event({"status": "artifact_json", "path": str(json_path)})
    except Exception as exc:
        from core.utils import log_step
        log_step("exports", "artifact_json_error", 
                {"error": str(exc)}, severity="warning")

    return pdf_path, csv_path, json_path


def export_report(
    consolidated: Dict[str, Any],
    first_event_id: Any,
    pdf_renderer: PdfRenderer,
    csv_exporter: CsvExporter,
    json_exporter: JsonExporter,
    fallback_pdf: PdfRenderer,
    fallback_csv: CsvExporter,
    fallback_json: JsonExporter,
    *,
    log_event: Callable[[Dict[str, Any]], None],
    log_step: Callable[[str, str, Dict[str, Any]], None],
) -> Tuple[Path, Path, Path]:
    outdir = SETTINGS.exports_dir
    outdir.mkdir(parents=True, exist_ok=True)

    pdf_path = outdir / "report.pdf"
    csv_path = outdir / "data.csv"
    json_path = outdir / "data.json"

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

    pdf_path = pdf_renderer(rows, fields, meta_dict, pdf_path)
    csv_exporter(rows, csv_path)
    json_path = json_exporter(rows, json_path)

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
        if json_path.exists() and json_path.stat().st_size < 10:  # Account for empty array
            fallback_json([], json_path)
    except Exception as exc:
        from core.utils import log_step
        log_step("exports", "fallback_artifact_error", 
                {"error": str(exc)}, severity="warning")

    log_event({"event_id": first_event_id, "status": "artifact_pdf", "path": str(pdf_path)})
    log_event({"event_id": first_event_id, "status": "artifact_csv", "path": str(csv_path)})
    log_event({"event_id": first_event_id, "status": "artifact_json", "path": str(json_path)})
    log_step(
        "orchestrator",
        "report_generated",
        {"event_id": first_event_id, "path": str(pdf_path)},
    )

    return pdf_path, csv_path, json_path


__all__ = [
    "resolve_exporters",
    "create_idle_artifacts",
    "export_report",
]

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple


def resolve_exporters(
    pdf_renderer: Callable[[Dict[str, Any], Path], None] | None,
    csv_exporter: Callable[[List[Dict[str, Any]], Path], None] | None,
    *,
    test_mode: bool,
) -> Tuple[
    Callable[[Dict[str, Any], Path], None],
    Callable[[List[Dict[str, Any]], Path], None],
    Callable[[Dict[str, Any], Path], None],
    Callable[[List[Dict[str, Any]], Path], None],
]:
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

    outdir = Path(os.getenv("OUTPUT_DIR", "output")) / "exports"
    outdir.mkdir(parents=True, exist_ok=True)

    pdf_path = outdir / "report.pdf"
    csv_path = outdir / "data.csv"

    empty_report = {
        "fields": ["info"],
        "rows": [{"info": "No valid triggers in current window"}],
        "meta": {"reason": "no_triggers"},
    }

    try:
        pdf_render.render_pdf(empty_report, pdf_path)
        log_event({"status": "artifact_pdf", "path": str(pdf_path)})
    except Exception as exc:
        log_event(
            {
                "status": "artifact_pdf_error",
                "error": str(exc),
                "severity": "warning",
            }
        )

    try:
        csv_export.export_csv([], csv_path)
        log_event({"status": "artifact_csv", "path": str(csv_path)})
    except Exception as exc:
        log_event(
            {
                "status": "artifact_csv_error",
                "error": str(exc),
                "severity": "warning",
            }
        )

    return pdf_path, csv_path


def export_report(
    consolidated: Dict[str, Any],
    first_event_id: Any,
    pdf_renderer: Callable[[Dict[str, Any], Path], None],
    csv_exporter: Callable[[List[Dict[str, Any]], Path], None],
    fallback_pdf: Callable[[Dict[str, Any], Path], None],
    fallback_csv: Callable[[List[Dict[str, Any]], Path], None],
    *,
    log_event: Callable[[Dict[str, Any]], None],
    log_step: Callable[[str, str, Dict[str, Any]], None],
) -> Tuple[Path, Path]:
    outdir = Path(os.getenv("OUTPUT_DIR", "output")) / "exports"
    outdir.mkdir(parents=True, exist_ok=True)

    pdf_path = outdir / "report.pdf"
    csv_path = outdir / "data.csv"

    pdf_renderer(consolidated, pdf_path)
    csv_exporter(consolidated.get("rows", []), csv_path)

    try:
        if pdf_path.exists() and pdf_path.stat().st_size < 1000:
            fallback_pdf(
                {
                    "fields": ["info"],
                    "rows": [{"info": "invalid_artifact_detected"}],
                    "meta": {},
                },
                pdf_path,
            )
        if csv_path.exists() and csv_path.stat().st_size < 5:
            fallback_csv([], csv_path)
    except Exception:
        pass

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

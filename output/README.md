# Output

## Purpose
Rendering utilities for PDF and CSV dossier generation.

## Files
- `pdf_render.py`
- `csv_export.py`
- `templates/pdf/`
- `exports/pdf/`
- `exports/csv/`
- `examples/`: sample output files.

## Dependencies
`weasyprint` for PDF rendering and the Python standard library for CSV.

## Usage

Use `render_pdf(rows, fields, meta=None, out_path=None)` to render a PDF report
from table-style data. The function returns the :class:`pathlib.Path` of the
written file and defaults to `SETTINGS.exports_dir / "report.pdf"` when
`out_path` is omitted. Legacy code that previously called
`render_pdf(mapping, path)` should migrate to the new signature. A temporary
compatibility helper `render_pdf_from_mapping(mapping, path)` remains available
and now emits a `DeprecationWarning` on use.

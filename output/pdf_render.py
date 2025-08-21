"""PDF rendering using WeasyPrint."""

from __future__ import annotations

from html import escape
from pathlib import Path
import json

from weasyprint import HTML


def render_pdf(data: dict, output_path: Path) -> None:
    """Render ``data`` into a PDF at ``output_path``.

    The PDF uses a simple tabular layout and includes a header and footer on
    every page. ``output_path`` may be a :class:`str` or :class:`~pathlib.Path`.
    """

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for key, value in data.items():
        if key == "meta":
            continue
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, indent=2)
        else:
            value_str = str(value)
        rows.append(f"<tr><th>{escape(str(key))}</th><td>{escape(value_str)}</td></tr>")
    rows_html = "\n".join(rows)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8'>
    <style>
        @page {{
            size: A4;
            margin: 1in;
            @top-center {{
                content: 'A2A Research Report';
                font-weight: bold;
                font-size: 14pt;
            }}
            @bottom-center {{
                content: 'Page ' counter(page) ' of ' counter(pages);
                font-size: 10pt;
            }}
        }}
        body {{ font-family: sans-serif; font-size: 12pt; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ text-align: left; padding: 4px; border-bottom: 1px solid #ddd; }}
    </style>
</head>
<body>
    <h1>Research Report</h1>
    <table>
        {rows_html}
    </table>
</body>
</html>"""

    HTML(string=html).write_pdf(str(path))


__all__ = ["render_pdf"]

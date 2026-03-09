# report.py
from __future__ import annotations
import base64
from datetime import datetime,date
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from results import DepurationResult  # tus clases


def _build_context(result: DepurationResult) -> dict:
    """
    Convierte DepurationResult a un dict plano listo para Jinja2.
    Todos los valores son strings o listas de dicts — sin objetos custom.
    """
    offices_ctx = []
    for o in result.offices:
        sheets_ctx = []
        for s in o.sheets:
            errors_ctx = [
                {
                    "row":   e.row,
                    "col":   e.col,
                    "field": e.field,
                    "value": str(e.value) if e.value is not None else None,
                    "msg":   e.msg,
                }
                for e in s.registry.all_errors()
            ]
            sheets_ctx.append({
                "expected_name": s.expected_name,
                "matched_name":  s.matched_name,
                "headers_ok":    s.headers_ok,
                "errors":        errors_ctx,
            })

        total_errors = sum(len(s["errors"]) for s in sheets_ctx)
        offices_ctx.append({
            "office":       o.office,
            "file":         o.file_path.name,
            "sheets":       sheets_ctx,
            "total_errors": total_errors,
        })

    all_sheets        = [s for o in offices_ctx for s in o["sheets"]]
    sheets_with_errors = sum(1 for s in all_sheets if s["errors"])
    sheets_ok          = sum(1 for s in all_sheets if not s["errors"])
    total_errors       = sum(o["total_errors"] for o in offices_ctx)

    # Errores generales: extensible, por ahora solo solapamientos
    general_errors = []
    if result.overlaps:
        general_errors.append({
            "title": "Solapamientos de barcos",
            "type":  "overlaps",
            "entries": [
                {
                    "vessel": c.vessel,
                    "row_a":  c.row_a,
                    "row_b":  c.row_b,
                    "doa_a": c.row_a_data['doa'].strftime('%Y-%m-%d') if isinstance(c.row_a_data['doa'],date) else '' ,
                    "doa_b": c.row_b_data['doa'].strftime('%Y-%m-%d') if isinstance(c.row_b_data['doa'],date) else '' ,
                    "etc_a": c.row_a_data['etc'].strftime('%Y-%m-%d') if isinstance(c.row_a_data['etc'],date) else '' ,
                    "etc_b": c.row_b_data['etc'].strftime('%Y-%m-%d') if isinstance(c.row_b_data['etc'],date) else '' ,
                    'sheet_a': c.sheet_a,
                    'sheet_b': c.sheet_b,
                    "msg":    (
                        f"'{c.vessel}' se solapa entre fila {c.row_a} "
                        f"y fila {c.row_b}."
                    ),
                }
                for c in result.overlaps
            ],
        })

    return {
        "generated_at":       datetime.now().strftime("%d/%m/%Y %H:%M"),
        "offices":            offices_ctx,
        "total_errors":       total_errors,
        "sheets_with_errors": sheets_with_errors,
        "sheets_ok":          sheets_ok,
        "general_errors":     general_errors,
    }


def render_report(
    result:        DepurationResult,
    template_path: Path,
    output_path:   Path,
    embed_fonts:   bool = False,
    fonts_dir:     Path | None = None,
) -> Path:
    """
    Renderiza el reporte HTML a output_path.

    Args:
        result:        resultado de depurate_lineup_files()
        template_path: ruta al .j2
        output_path:   donde escribir el HTML final
        embed_fonts:   si True, embebe las TTF como base64 en el CSS
        fonts_dir:     carpeta con las TTF (requerido si embed_fonts=True)
    """
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template(template_path.name)

    ctx = _build_context(result)

    if embed_fonts:
        assert fonts_dir is not None, "fonts_dir requerido para embed_fonts=True"
        ctx["font_regular_b64"] = _font_b64(fonts_dir / "LiberationMono-Regular.ttf")
        ctx["font_bold_b64"]    = _font_b64(fonts_dir / "LiberationMono-Bold.ttf")

    html = template.render(**ctx)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _font_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()




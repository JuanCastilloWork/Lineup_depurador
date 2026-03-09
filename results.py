# results.py
from dataclasses import dataclass, field
from pathlib import Path
from error_registry import CellError, ErrorRegistry
from overlap import OverlapChecker, OverlapConflict, build_interval

@dataclass
class SheetResult:
    """Resultado del procesamiento de una hoja individual."""
    expected_name: str           # nombre esperado según config
    matched_name:  str           # nombre real encontrado en el archivo
    headers_ok:    bool          # si los headers pasaron verify_headers
    rows:          list[dict]    # filas validadas exitosamente
    registry:      ErrorRegistry # errores de esa hoja

    @property
    def has_errors(self) -> bool:
        return len(self.registry) > 0

    @property
    def total_rows(self) -> int:
        return len(self.rows)


@dataclass
class OfficeResult:
    """Resultado del procesamiento de un archivo/oficina completa."""
    office:    str            # clave de oficina ej. "BARRANQUILLA"
    file_path: Path           # path real del archivo matcheado
    sheets:    list[SheetResult] = field(default_factory=list)

    @property
    def all_rows(self) -> list[dict]:
        return [row for sheet in self.sheets for row in sheet.rows]

    @property
    def has_errors(self) -> bool:
        return any(s.has_errors for s in self.sheets)

    @property  
    def total_errors(self) -> int:
        return sum(len(s.registry) for s in self.sheets)

    def get_sheet(self, expected_name: str) -> SheetResult | None:
        return next((s for s in self.sheets if s.expected_name == expected_name), None)

@dataclass
class DepurationResult:
    """Contenedor raíz — agrega todas las oficinas + conflictos de solapamiento."""
    offices:   list[OfficeResult]        = field(default_factory=list)
    overlaps:  list[OverlapConflict]     = field(default_factory=list)  # de overlap.py

    @property
    def all_rows(self) -> list[dict]:
        return [row for office in self.offices for row in office.all_rows]

    @property
    def has_errors(self) -> bool:
        return any(o.has_errors for o in self.offices) or bool(self.overlaps)

    def get_office(self, office_key: str) -> OfficeResult | None:
        return next((o for o in self.offices if o.office == office_key), None)

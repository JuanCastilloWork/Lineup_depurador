
from dataclasses import dataclass, field
from pathlib import Path
from .error_registry import ErrorRegistry
from .vessel_overlap import OverlapChecker, OverlapConflict, build_interval
from typing import Any
from rapidfuzz import process,fuzz

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
class ColumnSetAccumulator:
    """Acumula valores únicos por columna durante la iteración fila a fila."""
    _data: dict[str, set] = field(default_factory=dict)

    def add(self, field_name: str, value: Any):
        if value is not None:
            self._data.setdefault(field_name, set()).add(value)

    def get(self, field_name: str) -> set:
        return self._data.get(field_name, set())

    def find_suspicious(
        self,
        field_name: str,
        reference_list: list[str],
        threshold: int = 100,
    ) -> list[dict]:
        """
        Compara los valores acumulados de `field_name` contra `reference_list`
        con rapidfuzz. Retorna los valores cuyo mejor match NO alcance `threshold`.

        Returns:
            [{"value": ..., "best_match": ..., "score": ...}, ...]
        """
        accumulated = self.get(field_name)
        if not accumulated or not reference_list:
            return []

        suspicious = []
        for value in accumulated:
            result = process.extractOne(
                str(value),
                [str(r) for r in reference_list],
                scorer=fuzz.ratio,
            )
            if result is None:
                suspicious.append({"value": value, "best_match": None, "score": 0})
                continue

            best_match, score, _ = result
            if score < threshold:
                suspicious.append({
                    "value":      value,
                    "best_match": best_match,
                    "score":      score,
                })
        return suspicious

FIELDS_TO_COMPARE = ["CHARTERER", "SHIPOWNER", "AGENCY", "VESSEL", "PORT_LOAD_DISCH"]

@dataclass
class DepurationResult:
    """Contenedor raíz — agrega todas las oficinas + conflictos de solapamiento."""
    offices:   list[OfficeResult]        = field(default_factory=list)
    overlaps:  list[OverlapConflict]     = field(default_factory=list)  # de overlap.py    
    unique_values : ColumnSetAccumulator = field(default_factory=ColumnSetAccumulator)

    def add_to_acumulator(self, field_name : str, value : Any):
        if field_name in FIELDS_TO_COMPARE:
            self.unique_values.add(field_name,value)
    def compare_fields(
        self,
        references: dict[str, list[str]],
        threshold: int = 100,
    ) -> dict[str, list[dict]]:
        """
        references = {
            "CHARTERER":      [...],
            "SHIPOWNER":      [...],
            "AGENCY":         [...],
            "VESSEL":         [...],
            "PORT_LOAD_DISCH": [...],
        }
        Retorna solo los campos que tienen valores sospechosos.
        """
        results = {}
        for field_name in FIELDS_TO_COMPARE:
            ref_list = references.get(field_name, [])
            suspicious = self.unique_values.find_suspicious(field_name, ref_list, threshold)
            if suspicious:
                results[field_name] = suspicious
        return results
    
    @property
    def all_rows(self) -> list[dict[str,Any]]:
        return [row for office in self.offices for row in office.all_rows]

    @property
    def has_errors(self) -> bool:
        return any(o.has_errors for o in self.offices) or bool(self.overlaps)

    def get_office(self, office_key: str) -> OfficeResult | None:
        return next((o for o in self.offices if o.office == office_key), None)    

__all__ = ['OfficeResult','DepurationResult','OverlapChecker','build_interval','SheetResult']

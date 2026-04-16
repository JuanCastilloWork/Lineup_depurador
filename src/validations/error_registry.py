
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

class WarningLevel(str, Enum):
   LOW = "low"
   MEDIUM = "medium"
   HIGH = "high"


class ErrorType(str, Enum):
   MISSING_VALUE = "missing_value"
   INVALID_FORMAT = "invalid_format"
   OUT_OF_RANGE = "out_of_range"
   INVALID_VALUE = "invalid_value"
   UNKNOWN = "unknown"


class WarningType(str, Enum):
   SUSPICIOUS_VALUE = "suspicious_value"
   COERCED_VALUE = "coerced_value"
   MISSING_OPTIONAL = "missing_optional"
   UNKNOWN = "unknown"

@dataclass
class CellError:
   vessel: str
   row_index: int
   column: str
   value: Any
   reason: str
   error_type: ErrorType = ErrorType.UNKNOWN

@dataclass
class CellWarning:
   vessel: str
   row_index: int
   column: str
   value: Any
   reason: str
   level: WarningLevel = WarningLevel.LOW
   warning_type: WarningType = WarningType.UNKNOWN


@dataclass
class ValidationReport:
   """
   Estructura principal de reporte de validación.

   Almacenamiento interno:
     - _errors / _warnings        → dict[column, list[Cell*]]  para acceso por columna O(1)
     - _errors_idx / _warnings_idx → dict[column, list[int]]   para acceso a índices O(1)
     - _errors_by_row             → dict[row, list[CellError]] se construye on-the-fly al agregar,
                                    pensado para la vista principal del reporte final
   """

   # por columna
   _errors: dict[str, list[CellError]] = field(default_factory=dict)
   _warnings: dict[str, list[CellWarning]] = field(default_factory=dict)

   # índices por columna — O(1) para el módulo que los necesita mucho
   _errors_idx: dict[str, list[int]] = field(default_factory=dict)
   _warnings_idx: dict[str, list[int]] = field(default_factory=dict)

   _errors_type : dict[ErrorType,int] = field(default_factory=dict)
   _warnings_type : dict[WarningType,int] = field(default_factory=dict)

   # --- mutación ---

   def add_error(
      self,
      vessel: str,
      row_index: int,
      column: str,
      value: Any,
      reason: str,
      error_type: ErrorType = ErrorType.UNKNOWN,
   ) -> None:
      error = CellError(vessel, row_index, column, value, reason, error_type)
      self._errors.setdefault(column, []).append(error)
      self._errors_idx.setdefault(column, []).append(row_index)
      self._errors_type[error_type] = self._errors_type.get(error_type, 0) + 1

   def add_warning(
      self,
      vessel: str,
      row_index: int,
      column: str,
      value: Any,
      reason: str,
      level: WarningLevel = WarningLevel.LOW,
      warning_type: WarningType = WarningType.UNKNOWN,
   ) -> None:
      warning = CellWarning(vessel, row_index, column, value, reason, level, warning_type)
      self._warnings.setdefault(column, []).append(warning)
      self._warnings_idx.setdefault(column, []).append(row_index)
      self._warnings_type[warning_type] = self._warnings_type.get(warning_type, 0) + 1
   # --- totales ---

   def total_errors(self) -> int:
      return sum(len(v) for v in self._errors.values())

   def total_warnings(self) -> int:
      return sum(len(v) for v in self._warnings.values())

   def rows_with_issues_count(self) -> tuple[int, int]:
      """
      Retorna la cantidad total de filas que tienen errores y advertencias.
      
      Retorna:
          tuple[int, int]: (filas_con_errores, filas_con_warnings)
      """
      # Juntamos todos los índices de todas las columnas en un set para eliminar duplicados
      unique_error_rows = set(
          row_idx for idx_list in self._errors_idx.values() for row_idx in idx_list
      )
      
      unique_warning_rows = set(
          row_idx for idx_list in self._warnings_idx.values() for row_idx in idx_list
      )
      
      return len(unique_error_rows), len(unique_warning_rows)
   def is_valid(self, include_warnings: bool = False) -> bool:
      if include_warnings:
         return self.total_errors() == 0 and self.total_warnings() == 0
      return self.total_errors() == 0

   def errors_grouped_by_row(self) -> dict[int, list[CellError]]:
      """Construye el agrupado fila → errores. Llamar solo al generar el reporte final."""
      result: dict[int, list[CellError]] = {}
      for errors in self._errors.values():
         for e in errors:
            result.setdefault(e.row_index, []).append(e)
      return result
   
   def errors_by_type_count(self):
      return self._errors_type

   def warnings_by_type_count(self):
      return self._warnings_type
   # --- índices por columna (O(1) — para el módulo que los necesita) ---

   def issues_by_vessel_and_row(self)->dict[str,dict[int,dict[str,list]]]:
      """
      Construye una estructura agrupada por buque y fila, ordenando los índices ascendentemente.
      
      Retorna:
          {
              "Nombre Buque": {
                  10: {"errors": [CellError, ...], "warnings": [CellWarning, ...]},
                  15: {"errors": [], "warnings": [...]}
              }
          }
      """
      result: dict[str, dict[int, dict[str, list]]] = {}

      # 1. Poblar errores
      for errors in self._errors.values():
         for e in errors:
            vessel_dict = result.setdefault(e.vessel, {})
            row_dict = vessel_dict.setdefault(e.row_index, {"errors": [], "warnings": []})
            row_dict["errors"].append(e)

      # 2. Poblar warnings
      for warnings in self._warnings.values():
         for w in warnings:
            vessel_dict = result.setdefault(w.vessel, {})
            row_dict = vessel_dict.setdefault(w.row_index, {"errors": [], "warnings": []})
            row_dict["warnings"].append(w)

      # 3. Ordenar por row_index (movimientos) de manera ascendente
      sorted_result = {}
      for vessel, rows in result.items():
         # En Python 3.7+, los diccionarios mantienen el orden de inserción.
         # Ordenamos por la llave (row_index)
         sorted_result[vessel] = dict(sorted(rows.items()))

      return sorted_result      
      
   def idx_errors_by_column(self, column: str) -> list[int]:
      return self._errors_idx.get(column, [])

   def idx_warnings_by_column(self, column: str) -> list[int]:
      return self._warnings_idx.get(column, [])

   # --- por columna ---

   def errors_by_column(self, column: str) -> list[CellError]:
      return self._errors.get(column, [])

   def warnings_by_column(self, column: str) -> list[CellWarning]:
      return self._warnings.get(column, [])

   # --- por tipo / nivel (O(n) — uso puntual) ---

   def errors_by_type(self, error_type: ErrorType) -> list[CellError]:
      return [e for col in self._errors.values() for e in col if e.error_type == error_type]

   def warnings_by_type(self, warning_type: WarningType) -> list[CellWarning]:
      return [w for col in self._warnings.values() for w in col if w.warning_type == warning_type]

   def warnings_by_level(self, level: WarningLevel) -> list[CellWarning]:
      return [w for col in self._warnings.values() for w in col if w.level == level]

   
   def error_count_by_type(self, error_type: ErrorType) -> int:
      return self._errors_type.get(error_type, 0)
   
   def warning_count_by_type(self, warning_type: WarningType) -> int:
      return self._warnings_type.get(warning_type, 0)
   # --- flat lists ---

   @property
   def all_errors(self) -> list[CellError]:
      return [e for col in self._errors.values() for e in col]

   @property
   def all_warnings(self) -> list[CellWarning]:
      return [w for col in self._warnings.values() for w in col]

__all__ = [
    "ValidationReport",
    "CellError",
    "CellWarning",
    "ErrorType",
    "WarningType",
    "WarningLevel",
]

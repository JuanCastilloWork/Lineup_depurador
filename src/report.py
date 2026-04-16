from dataclasses import dataclass, field
from typing import Any

@dataclass
class CellError:
   row_index : int
   column : str
   value : Any
   reason : str

@dataclass
class CellWarning:
   row_index : int
   column : str
   value : Any
   reason : str
   level : str # Podemos poner alto o alguna cosita

@dataclass
class ValidationReport:
   errors : list[CellError] = field(default_factory=list)
   warnings : list[CellWarning] = field(default_factory=list)
   
   def add_error(self, row_index: int, column: str, value: Any, reason: str) -> None:
      self.errors.append(CellError(row_index, column, value, reason))

   def add_warning(self, row_index : int , column : str , value : Any, reason : str, level : str)->None:
      self.warnings.append(CellWarning(row_index,column,value,reason,level))

   def is_valid(self, include_warnings : bool = False) -> bool:
      if not include_warnings:
         return len(self.errors) == 0
      return len(self.errors) == 0 or len(self.warnings) == 0

   def by_column(self, column: str) -> list[CellError]:
      return [e for e in self.errors if e.column == column]

   def invalid_indices(self, column: str) -> list[int]:
      """Índices sin error en esa columna — para comparar entre columnas"""
      bad = {e.row_index for e in self.by_column(column)}
      return [e.row_index for e in self.errors if e.row_index in bad]

   def by_row(self) -> dict[int, list[CellError]]:
      """Agrupa por fila — para el reporte final fila x columna"""
      result: dict[int, list[CellError]] = {}
      for e in self.errors:
         result.setdefault(e.row_index, []).append(e)
      return result
   

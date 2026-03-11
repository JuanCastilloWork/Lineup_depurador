from dataclasses import dataclass,field
from typing import Any
from collections import defaultdict

@dataclass
class CellError:
   row: int
   col: int
   field: str
   msg: str
   value: Any = None
   source: str = "pydantic"

class ErrorRegistry:
   def __init__(self):
      # índice primario: fila → lista de CellError
      self._by_row: dict[int, list[CellError]] = defaultdict(list)
      # índice secundario: col → set de filas que tienen errores en esa col (Guardando referencia a la fila)
      self._col_index: dict[int, set[int]] = defaultdict(set)

   def add(self, row : int, col : int, field : str, msg : str, value : Any = None, source : str = 'pydantic') -> None:
      error = CellError(row,col,field,msg,value,source)
      self._by_row[error.row].append(error)
      self._col_index[error.col].add(error.row)
      
   def get_by_row(self, row: int) -> list[CellError]:
      return self._by_row.get(row, [])

   def get_by_col(self, col: int) -> list[CellError]:
      rows_with_errors = self._col_index.get(col, set())
      return [
          err
          for row in rows_with_errors
          for err in self._by_row[row]
          if err.col == col
      ]
   
   def get_by_cell(self, row: int, col: int) -> list[CellError]:
      return [e for e in self._by_row.get(row, []) if e.col == col]

   def has_errors(self, row: int) -> bool:
      return bool(self._by_row.get(row))

   def all_errors(self) -> list[CellError]:
      return [err for errors in self._by_row.values() for err in errors]

   def __len__(self) -> int:
      return sum(len(v) for v in self._by_row.values())

   def __repr__(self) -> str:
      return f"ErrorRegistry({len(self)} errores en {len(self._by_row)} filas)"

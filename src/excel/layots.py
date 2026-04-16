
"""
src/excel/layouts.py

Define los layouts de columnas usados para leer y generar reportes de Line Up
desde archivos Excel. Cada layout es un Enum cuyos miembros describen una
columna: su posición (índice entero), su encabezado esperado y el tipo de dato
ideal que debería contener.

Layouts de carga (input):
   - LineUpLayout         → layout estándar de la mayoría de puertos
   - LineUpVariantLayout  → variante con columna WINDOWS y unidades en BBLS

Layouts de reporte (output):
   - LineUpReportLayout        → reporte final para clientes (versión estándar)
   - LineUpReportVariantLayout → reporte final para clientes (versión BBLS)

Agrupación:
   - LayoutBundle   → par (load, report) de layouts relacionados
   - LineUpLayouts  → punto de entrada principal del módulo
"""
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Generic, TypeVar
from openpyxl.utils import column_index_from_string

@dataclass(frozen=True)
class ColDef:
   col: int
   name: str
   ideal_type : str = 'string'

def _col(letter: str, name: str, ideal_type : str = 'string') -> ColDef:
   """Helper interno para definir columnas desde letras Excel"""
   return ColDef(column_index_from_string(letter), name,ideal_type)

class Headers:
   VESSEL                 = "VESSEL"
   DATE_OF_ARRIVAL        = "DATE OF ARRIVAL"
   DATE_OF_ARRIVAL_PERIOD = "DATE OF ARRIVAL PERIOD"
   ETB                    = "ETB"
   ETB_PERIOD             = "ETB PERIOD"
   PIER                   = "PIER"
   ETC                    = "ETC"
   ETC_PERIOD             = "ETC PERIOD"
   TERMINAL               = "TERMINAL"
   STATUS                 = "STATUS"
   AGENCY                 = "AGENCY"
   CHARTERER              = "CHARTERER"
   SHIPOWNER              = "SHIPOWNER"
   OPERATION              = "OPERATION"
   TYPE                   = "TYPE"
   PRODUCT                = "PRODUCT"
   PORT_LOAD_DISCH        = "PORT LOAD/DISCH"

_H = Headers

class Columns:
   VESSEL                 = "VESSEL"
   DATE_OF_ARRIVAL        = "DATE_OF_ARRIVAL"
   DATE_OF_ARRIVAL_PERIOD = "DATE_OF_ARRIVAL_PERIOD"
   ETB                    = "ETB"
   ETB_PERIOD             = "ETB_PERIOD"
   PIER                   = "PIER"
   ETC                    = "ETC"
   ETC_PERIOD             = "ETC_PERIOD"
   TERMINAL               = "TERMINAL"
   STATUS                 = "STATUS"
   AGENCY                 = "AGENCY"
   CHARTERER              = "CHARTERER"
   SHIPOWNER              = "SHIPOWNER"
   OPERATION              = "OPERATION"
   TYPE                   = "TYPE"
   PRODUCT                = "PRODUCT"
   PORT_LOAD_DISCH        = "PORT_LOAD_DISCH"
   MT_BY_PRODUCT          = "MT_BY_PRODUCT"
   TOTAL_MT               = "TOTAL_MT"

class LineUpBaseLayout(Enum):
   ...

   @property
   def col(self) -> int:
      return self.value.col

   @property
   def header(self) -> str:
      return self.value.name

   @property
   def ideal_type(self)->str:
      return self.value.ideal_type

   @classmethod
   def get_sorted(cls):
      return sorted(cls, key=lambda m: m.col)
   
   @classmethod
   def col_range(cls, layout_sorted : list[LineUpBaseLayout]| None = None):
      if layout_sorted is not None:
         return layout_sorted[0].col, layout_sorted[-1].col

      members = cls.get_sorted()      
      return members[0].col, members[-1].col

class LineUpLayout(LineUpBaseLayout):
   VESSEL                 = _col("B", _H.VESSEL)
   DATE_OF_ARRIVAL        = _col("C", _H.DATE_OF_ARRIVAL, 'datetime')
   DATE_OF_ARRIVAL_PERIOD = _col("D", _H.DATE_OF_ARRIVAL_PERIOD)
   ETB                    = _col("E", _H.ETB, 'datetime')
   ETB_PERIOD             = _col("F", _H.ETB_PERIOD)
   PIER                   = _col("G", _H.PIER)
   ETC                    = _col("H", _H.ETC, 'datetime')
   ETC_PERIOD             = _col("I", _H.ETC_PERIOD)
   TERMINAL               = _col("J", _H.TERMINAL)
   STATUS                 = _col("K", _H.STATUS)
   AGENCY                 = _col("L", _H.AGENCY)
   CHARTERER              = _col("M", _H.CHARTERER)
   SHIPOWNER              = _col("N", _H.SHIPOWNER)
   OPERATION              = _col("O", _H.OPERATION)
   TYPE                   = _col("P", _H.TYPE)
   PRODUCT                = _col("Q", _H.PRODUCT)
   MT_BY_PRODUCT          = _col("R", "MT BY PRODUCT")
   TOTAL_MT               = _col("S", "TOTAL MT", 'decimal')
   PORT_LOAD_DISCH        = _col("T", _H.PORT_LOAD_DISCH)

class LineUpReportLayout(LineUpBaseLayout):
   VESSEL          = _col("B", _H.VESSEL)
   DATE_OF_ARRIVAL = _col("C", _H.DATE_OF_ARRIVAL, 'date')
   ETB             = _col("D", _H.ETB, 'date')
   PIER            = _col("E", _H.PIER)
   ETC             = _col("F", _H.ETC, 'date')
   TERMINAL        = _col("G", _H.TERMINAL)
   STATUS          = _col("H", _H.STATUS)
   AGENCY          = _col("I", _H.AGENCY)
   CHARTERER       = _col("J", _H.CHARTERER)
   SHIPOWNER       = _col("K", _H.SHIPOWNER)
   OPERATION       = _col("L", _H.OPERATION)
   TYPE            = _col("M", _H.TYPE)
   PRODUCT         = _col("N", _H.PRODUCT)
   MT_BY_PRODUCT   = _col("O", "MT BY PRODUCT")
   TOTAL_MT        = _col("P", "TOTAL MT", 'decimal')
   PORT_LOAD_DISCH = _col("Q", _H.PORT_LOAD_DISCH)

class LineUpVariantLayout(LineUpBaseLayout):
   VESSEL                 = _col("B", _H.VESSEL)
   WINDOWS                = _col("C", "WINDOWS")
   DATE_OF_ARRIVAL        = _col("D", _H.DATE_OF_ARRIVAL, 'datetime')
   DATE_OF_ARRIVAL_PERIOD = _col("E", _H.DATE_OF_ARRIVAL_PERIOD)
   ETB                    = _col("F", _H.ETB, 'datetime')
   ETB_PERIOD             = _col("G", _H.ETB_PERIOD)
   PIER                   = _col("H", _H.PIER)
   ETC                    = _col("I", _H.ETC, 'datetime')
   ETC_PERIOD             = _col("J", _H.ETC_PERIOD)
   TERMINAL               = _col("K", _H.TERMINAL)
   STATUS                 = _col("L", _H.STATUS)
   AGENCY                 = _col("M", _H.AGENCY)
   CHARTERER              = _col("N", _H.CHARTERER)
   SHIPOWNER              = _col("O", _H.SHIPOWNER)
   OPERATION              = _col("P", _H.OPERATION)
   TYPE                   = _col("Q", _H.TYPE)
   PRODUCT                = _col("R", _H.PRODUCT)
   MT_BY_PRODUCT          = _col("S", "BBLS BY PRODUCT")
   TOTAL_MT               = _col("T", "BBLS TOTAL", 'decimal')
   PORT_LOAD_DISCH        = _col("U", _H.PORT_LOAD_DISCH)

class LineUpReportVariantLayout(LineUpBaseLayout):
   VESSEL          = _col("B", _H.VESSEL)
   WINDOWS         = _col("C", "WINDOWS")
   DATE_OF_ARRIVAL = _col("D", _H.DATE_OF_ARRIVAL, 'date')
   ETB             = _col("E", _H.ETB, 'date')
   PIER            = _col("F", _H.PIER)
   ETC             = _col("G", _H.ETC, 'date')
   TERMINAL        = _col("H", _H.TERMINAL)
   STATUS          = _col("I", _H.STATUS)
   AGENCY          = _col("J", _H.AGENCY)
   CHARTERER       = _col("K", _H.CHARTERER)
   SHIPOWNER       = _col("L", _H.SHIPOWNER)
   OPERATION       = _col("M", _H.OPERATION)
   TYPE            = _col("N", _H.TYPE)
   PRODUCT         = _col("O", _H.PRODUCT)
   MT_BY_PRODUCT   = _col("P", "BBLS BY PRODUCT")
   TOTAL_MT        = _col("Q", "BBLS TOTAL", 'decimal')
   PORT_LOAD_DISCH = _col("R", _H.PORT_LOAD_DISCH)

L = TypeVar("L", bound=LineUpBaseLayout)
R = TypeVar("R", bound=LineUpBaseLayout)

class LayoutBundle(Generic[L, R]):
   def __init__(self, load: type[L], report: type[R]) -> None:
      self.load: type[L] = load
      self.report: type[R] = report

class LineUpLayouts(Generic[L,R]):
   base = LayoutBundle(LineUpLayout,LineUpReportLayout)
   variant = LayoutBundle(LineUpVariantLayout,LineUpReportVariantLayout)

__all__ = [
   "Headers",
   "LineUpBaseLayout",
   "LineUpLayouts",
   "LineUpLayout",
   "LineUpVariantLayout", 
   "LineUpReportLayout",
   "LineUpReportVariantLayout",
   "LayoutBundle",
   "L",
   "R"
]

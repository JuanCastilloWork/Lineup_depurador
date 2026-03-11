# Modulo donde dejamos los layouts que tiene el line up, tanto al momento de carga del archivo como
# Al momenot de hacer reportes

from enum import Enum
from typing import Any

class ColDef:
   """
   Definicion de una columna, indicando el indice (base 1 como openpyxl) y el nombre correspondiente
   """
   def __init__(self, col: int, label: str):
      self.col = col
      self.label = label

   def __repr__(self):
      return f"ColDef(col={self.col}, label='{self.label}')"
   
class LineUpLayout(Enum):
   """
   Layout principal del lineup, es el que esta en la mayoria de puertos
   """
   VESSEL          = ColDef(2,  "VESSEL")
   DATE_OF_ARRIVAL = ColDef(3,  "DATE OF ARRIVAL")
   DATE_OF_ARRIVAL_PERIOD = ColDef(4,  "DATE OF ARRIVAL PERIOD")
   ETB             = ColDef(5,  "ETB")
   ETB_PERIOD             = ColDef(6,  "ETB PERIOD")
   PIER            = ColDef(7,  "PIER")
   ETC             = ColDef(8,  "ETC")
   ETC_PERIOD             = ColDef(9,  "ETC PERIOD")
   TERMINAL        = ColDef(10,  "TERMINAL")
   STATUS          = ColDef(11,  "STATUS")
   AGENCY          = ColDef(12,  "AGENCY")
   CHARTERER       = ColDef(13, "CHARTERER")
   SHIPOWNER       = ColDef(14, "SHIPOWNER")
   OPERATION       = ColDef(15, "OPERATION")
   TYPE            = ColDef(16, "TYPE")
   PRODUCT         = ColDef(17, "PRODUCT")
   MT_BY_PRODUCT   = ColDef(18, "MT BY PRODUCT")
   TOTAL_MT        = ColDef(19, "TOTAL MT")
   PORT_LOAD_DISCH = ColDef(20, "PORT LOAD/DISCH")

   @property
   def col(self) -> int:
      return self.value.col

   @property
   def label(self) -> str:
      return self.value.label

class LineUpReportLayout(Enum):
   """
   Layout principal para el reporte de clientes, corresponde a las columnas que se van a usar en el reporte final y su orden 
   """
   VESSEL          = ColDef(2,  "VESSEL")
   DATE_OF_ARRIVAL = ColDef(3,  "DATE OF ARRIVAL")
   ETB             = ColDef(4,  "ETB")
   PIER            = ColDef(5,  "PIER")
   ETC             = ColDef(6,  "ETC")
   TERMINAL        = ColDef(7, "TERMINAL")
   STATUS          = ColDef(8, "STATUS")
   AGENCY          = ColDef(9, "AGENCY")
   CHARTERER       = ColDef(10, "CHARTERER")
   SHIPOWNER       = ColDef(11, "SHIPOWNER")
   OPERATION       = ColDef(12, "OPERATION")
   TYPE            = ColDef(13, "TYPE")
   PRODUCT         = ColDef(14, "PRODUCT")
   MT_BY_PRODUCT   = ColDef(15, "MT BY PRODUCT")
   TOTAL_MT        = ColDef(16, "TOTAL MT")
   PORT_LOAD_DISCH = ColDef(17, "PORT LOAD/DISCH")

   @property
   def col(self) -> int:
      return self.value.col

   @property
   def label(self) -> str:
      return self.value.label

class LineUpLayoutVariant(Enum):
   """
   Segundo layout que tiene el lineup, cambiando unos nombres de columnas y adicionando la columna windows 
   """
   VESSEL          = ColDef(2,  "VESSEL")
   WINDOWS         = ColDef(3,  "WINDOWS")

   DATE_OF_ARRIVAL = ColDef(4,  "DATE OF ARRIVAL")
   DATE_OF_ARRIVAL_PERIOD = ColDef(5,  "DATE OF ARRIVAL PERIOD")

   ETB             = ColDef(6,  "ETB")
   ETB_PERIOD      = ColDef(7,  "ETB PERIOD")

   PIER            = ColDef(8,  "PIER")

   ETC             = ColDef(9,  "ETC")
   ETC_PERIOD      = ColDef(10, "ETC PERIOD")

   TERMINAL        = ColDef(11, "TERMINAL")
   STATUS          = ColDef(12, "STATUS")
   AGENCY          = ColDef(13, "AGENCY")
   CHARTERER       = ColDef(14, "CHARTERER")
   SHIPOWNER       = ColDef(15, "SHIPOWNER")
   OPERATION       = ColDef(16, "OPERATION")
   TYPE            = ColDef(17, "TYPE")
   PRODUCT         = ColDef(18, "PRODUCT")
   MT_BY_PRODUCT   = ColDef(19, "BBLS BY PRODUCT")
   TOTAL_MT        = ColDef(20, "BBLS TOTAL")
   PORT_LOAD_DISCH = ColDef(21, "PORT LOAD/DISCH")

   @property
   def col(self) -> int:
      return self.value.col

   @property
   def label(self) -> str:
      return self.value.label

class LineUpReportLayoutVariant(Enum):
   """
   Variante del reporte del line up 
   """
   VESSEL          = ColDef(2,  "VESSEL")
   WINDOWS         = ColDef(3,  "WINDOWS")

   DATE_OF_ARRIVAL = ColDef(4,  "DATE OF ARRIVAL")

   ETB             = ColDef(5,  "ETB")

   PIER            = ColDef(6,  "PIER")

   ETC             = ColDef(7,  "ETC")

   TERMINAL        = ColDef(8, "TERMINAL")
   STATUS          = ColDef(9, "STATUS")
   AGENCY          = ColDef(10, "AGENCY")
   CHARTERER       = ColDef(11, "CHARTERER")
   SHIPOWNER       = ColDef(12, "SHIPOWNER")
   OPERATION       = ColDef(13, "OPERATION")
   TYPE            = ColDef(14, "TYPE")
   PRODUCT         = ColDef(15, "PRODUCT")
   MT_BY_PRODUCT   = ColDef(16, "BBLS BY PRODUCT")
   TOTAL_MT        = ColDef(17, "BBLS_TOTAL")
   PORT_LOAD_DISCH = ColDef(18, "PORT LOAD/DISCH")

   @property
   def col(self) -> int:
      return self.value.col

   @property
   def label(self) -> str:
      return self.value.label

def row_to_dict( row : tuple, layout : type[LineUpReportLayout] | type[LineUpLayoutVariant])->dict[str, Any]:
   return {
      member.name: (row[member.col - 1] if member.col - 1 < len(row) else None)
      for member in layout
   }


from enum import Enum
class ColDef:
   """Definición de una columna: posición (1-indexed, como openpyxl) y nombre semántico."""
   def __init__(self, col: int, label: str):
      self.col = col
      self.label = label

   def __repr__(self):
      return f"ColDef(col={self.col}, label='{self.label}')"
   
# ---------------------------------------------------------------------------
# Layout B — con WINDOWS y métricas en BBLS
# Empieza en col B (2), header en fila 12
# B=VESSEL  C=WINDOWS  D=DATE OF ARRIVAL  E=ETB  F=PIER  G=ETC  H=TERMINAL
# I=STATUS  J=AGENCY   K=CHARTERER        L=SHIPOWNER        M=OPERATION
# N=TYPE    O=PRODUCT  P=BBLS BY PRODUCT  Q=BBLS TOTAL       R=PORT LOAD/DISCH
# ---------------------------------------------------------------------------

class LayoutB(Enum):
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
   MT_BY_PRODUCT   = ColDef(19, "MT BY PRODUCT")
   TOTAL_MT        = ColDef(20, "TOTAL MT")
   PORT_LOAD_DISCH = ColDef(21, "PORT LOAD/DISCH")

   @property
   def col(self) -> int:
      return self.value.col

   @property
   def label(self) -> str:
      return self.value.label

class ReportLayoutB(Enum):
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
   MT_BY_PRODUCT   = ColDef(16, "MT BY PRODUCT")
   TOTAL_MT        = ColDef(17, "TOTAL MT")
   PORT_LOAD_DISCH = ColDef(18, "PORT LOAD/DISCH")

   @property
   def col(self) -> int:
      return self.value.col

   @property
   def label(self) -> str:
      return self.value.label

# ---------------------------------------------------------------------------
# Layout A — sin WINDOWS, métricas en MT
# B=VESSEL  C=DATE OF ARRIVAL  D=ETB  E=PIER  F=ETC  G=TERMINAL
# H=STATUS  I=AGENCY  J=CHARTERER  K=SHIPOWNER  L=OPERATION
# M=TYPE  N=PRODUCT  O=MT BY PRODUCT  P=TOTAL MT  Q=PORT LOAD/DISCH
# ---------------------------------------------------------------------------
class LayoutA(Enum):
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


class ReportLayoutA(Enum):
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

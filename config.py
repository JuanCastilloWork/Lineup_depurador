from layout import LayoutA,LayoutB
from typing import Type

OFFICES : list[str] = ['SANTA MARTA','BUENAVENTURA','BARRANQUILLA','TOLÚ','CARTAGENA']
EXPECTED_SHEETS : dict[str,list[str]]= {
   'BUENAVENTURA':['BUENAVENTURA'],
   'TOLÚ':['TOLU','COVEÑAS']
}
MIN_MATCH_SCORE : int = 75 # Esto controla las coincidencias (archivos y hojas)

MAIN_LAYOUT = LayoutA
SECONDARY_LAYOUT = LayoutB
HEADER_ROW : int = 12 # Donde empieza el header en el archivo?

TERMINAL_LAYOUTS : dict[str,type[MAIN_LAYOUT] | type[SECONDARY_LAYOUT]] = {
   'COVEÑAS': SECONDARY_LAYOUT
}

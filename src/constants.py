from typing import Type
import excel
from enum import Enum

OFFICES : list[str] = ['SANTA MARTA','BUENAVENTURA','BARRANQUILLA','TOLÚ','CARTAGENA']
EXPECTED_SHEETS : dict[str,list[str]]= {
   'BUENAVENTURA':['BUENAVENTURA'],
   'TOLÚ':['TOLU','COVEÑAS']
}
MIN_MATCH_SCORE : int = 75 # Esto controla las coincidencias (archivos y hojas)
HEADER_ROW : int = 12 # Donde empieza el header en el archivo?

PORT_LAYOUTS : dict[str,type[excel.LineUpLayout] | type[excel.LineUpLayoutVariant]] = {
   'COVEÑAS': excel.LineUpLayoutVariant
}

REPORT_LAYOUTS : dict[str,type[excel.LineUpReportLayout]| type[excel.LineUpReportLayoutVariant]] = {
   'COVEÑAS' : excel.LineUpReportLayoutVariant
}


# COAL,CLINKER/CEMENT Y GRAINS, tienen que tener MT_BY_PRODCT,total y tipo de producto cuando zarpa, las otras puede ser el mismo producto
class TypeEnum(str, Enum):
   CLINKER_CEMENT  = "CLINKER/CEMENT"
   COAL            = "COAL" 
   CRUDE           = "CRUDE"
   DRY_PRODUCTS    = "DRY PRODUCTS"
   EDIBLE_OIL      = "EDIBLE OIL"
   FERTILIZERS     = "FERTILIZERS"
   GRAINS          = "GRAINS"
   LIQUID_CHEMS    = "LIQUID/CHEMS"
   LIVESTOCK       = "LIVESTOCK"
   OTHERS          = "OTHERS"
   PROJECT_CARGO   = "PROJECT CARGO"
   STEEL           = "STEEL"


from openpyxl.worksheet.worksheet import Worksheet
from rapidfuzz import process,fuzz
import logging
import excel

logger = logging.getLogger()

def find_best_sheet_match(sheet_names : list[str], expected_name : str,min_score : int )->str | None:
   result = process.extractOne(expected_name,sheet_names, scorer= fuzz.WRatio)
   if result is None:
      logger.warning(
         "No se encontró ninguna hoja para '%s'. Hojas disponibles: %s",
         expected_name,
         sheet_names,
      )
      return None
   matched_name,score,_ = result
   if score < min_score:
      logger.warning(
         "Mejor coincidencia para '%s' fue '%s' con score %d (mínimo requerido: %d). "
         "Se retorna None.",
         expected_name,
         matched_name,
         score,
         min_score,
      )
      return None
   if matched_name != expected_name:
      logger.info(
         "Hoja '%s' resuelta como '%s' (score: %d).",
         expected_name,
         matched_name,
         score,
      )
   return matched_name
   

def verify_headers(ws: Worksheet, layout: type[excel.LineUpLayout] | type[excel.LineUpLayoutVariant], header_row: int, min_score: int = 85) -> bool:
   """
   Verifica que los headers de la hoja Excel correspondan con el layout esperado.
   Compara cada columna definida en el layout contra el valor real en la fila header_row.
   
   Returns:
       True  — todos los headers pasaron el umbral mínimo
       False — al menos un header falló (se loguean los detalles)
   """
   all_ok = True

   for member in layout:
      expected_label = member.label
      col            = member.col
      cell_value     = ws.cell(row=header_row, column=col).value

      if cell_value is None:
         logger.warning(
             "Header faltante en col %d: se esperaba '%s', celda vacía.",
             col, expected_label,
         )
         all_ok = False
         continue

      actual = str(cell_value).strip()
      score  = fuzz.WRatio(expected_label.upper(), actual.upper())

      if score < min_score:
         logger.warning(
             "Header col %d no coincide: esperado='%s', encontrado='%s', score=%d (mínimo=%d).",
             col, expected_label, actual, score, min_score,
         )
         all_ok = False
      else:
         if actual.upper() != expected_label.upper():
             logger.info(
                 "Header col %d resuelto: esperado='%s', encontrado='%s' (score=%d).",
                 col, expected_label, actual, score,
             )

   return all_ok

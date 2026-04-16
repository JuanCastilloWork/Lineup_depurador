"""
src/excel/resolver.py

Entrada del modulo, donde se tiene el manager para cargar archivos de excel usando fuzzy matching pa todo
 
"""

from __future__ import annotations

from pathlib import Path
from openpyxl import Workbook
from .file_matching import find_best_file_match,find_best_sheet_match
import logging

logger = logging.getLogger(__name__)

class ExcelResolver:
   def __init__(self, folder : Path) -> None:
      self._folder = folder

   def get_excel_paths(self) -> list[Path]:
      """Retorna todos los archivos Excel del folder usando glob."""
      return [
          *self._folder.glob("*.xlsx"),
          *self._folder.glob("*.xls"),
          *self._folder.glob("*.xlsm"),
      ]

   def change_folder(self, folder : Path):
      logger.info('Se cambio el folder')
      self._folder = folder

   def match_files(self, expected_names : list[str], min_score : int = 80)->dict[str,Path]:

      """
      Dado una lista de nombres ideales que debe de cumplir un archivo, en la ruta establecida se retornan los matcheos
      """

      excel_paths = self.get_excel_paths()
      if len(expected_names) > len(excel_paths):
         logger.warning(
            "Se esperan %d archivos pero solo hay %d Excel en '%s'. "
            "Se intentará matchear los disponibles.",
            len(expected_names),
            len(excel_paths),
            self._folder,
         )

      available : dict[str,Path] = {p.stem:p for p in excel_paths}
      result : dict[str,Path] = {}

      for expected in expected_names:
         matched_name = find_best_file_match(
            list(available.keys()),expected,min_score
         )
         if matched_name is None:
            continue
         result[expected] = available.pop(matched_name)

      return result
      
   def match_sheets(
    self,
    wb: Workbook,
    expected_names: list[str],
    min_score: int = 80,
) -> dict[str, str]:
      """
      Dado un workbook abierto y una lista de nombres ideales de hojas,
      retorna un dict:
          { nombre_ideal: nombre_real_en_wb }

      Solo incluye los que tuvieron match exitoso.
      Un sheet ya matcheado no se reutiliza para siguientes búsquedas.
      """
      available: list[str] = list(wb.sheetnames)
      result: dict[str, str] = {}

      if len(expected_names) > len(available):
         logger.warning(
            "Se esperan %d hojas pero solo hay %d en el workbook. "
            "Se intentará matchear las disponibles.",
            len(expected_names),
            len(available),
         )

      for expected in expected_names:
         matched_name = find_best_sheet_match(available, expected, min_score)

         if matched_name is None:
            continue

         result[expected] = matched_name
         available.remove(matched_name)

      return result

__all__ = ['ExcelResolver']

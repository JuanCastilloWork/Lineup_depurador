from __future__ import annotations
 
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
 
import pandas as pd
import numpy as np
from rapidfuzz import fuzz, process
 
from validations.date_overlap import OverlapConflict, check_overlaps
from validations.error_registry import ValidationReport
from excel.layots import LineUpBaseLayout, Columns
from .utils import _to_decimal

if TYPE_CHECKING:
   from additional_data import LineUpValidationsData
 
logger = logging.getLogger(__name__)
 
 
# ---------------------------------------------------------------------------
# PortBundle — reemplaza los tres dicts separados (port_result / port_report /
# port_layouts) con una sola estructura por puerto.
# ---------------------------------------------------------------------------


_MONTH_ABBR = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
    5: "MAY", 6: "JUN", 7: "JUL", 8: "AUG",
    9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
} 
@dataclass
class PortBundle:
   port: str
   df: pd.DataFrame
   report: ValidationReport
   layout: type[LineUpBaseLayout]

class PostProcessor:
   """
   Validaciones y matching a nivel global (cross-puerto).
 
   Recibe un dict[str, PortBundle] con los resultados ya procesados por
   el primer processor y aplica:
     - Detección de solapamientos entre barcos (check_overlaps)
     - Company matching  (charterer / owner / agency)
     - Port matching
     - Vessel matching
 
   Expone:
     - run()                    → ejecuta todo el pipeline
     - match_report (property)  → dict listo para render_validation_report
     - get_port_dataframes()    → dict[str, pd.DataFrame] para LineUpExcelReport
                                  (sin columnas auxiliares, tipos Excel-friendly)
   """
   def __init__(
      self,
      bundles: dict[str, PortBundle],
      config: dict,
      validation_data: "LineUpValidationsData",
      row_offset: int = 12,
    ) -> None:
      self._bundles = bundles
      self._config = config
      self._validation_data = validation_data
      self._row_offset = row_offset
 
      self._match_report: dict = {
          "companies": [],
          "ports": [],
          "vessels": [],
      }
      self._vessel_conflicts : list[OverlapConflict] = []
 
      # DataFrame global (concatenación de todos los puertos)
      self._df: pd.DataFrame = pd.DataFrame()

   @property
   def match_report(self)->dict:
      return self._match_report

   def run(self) -> None:
      """Ejecuta el pipeline completo de post-procesamiento."""
      self._build_global_df()
      self._check_overlaps()
      self._run_company_matching()
      self._run_port_matching()
      self._run_vessel_matching()

   def get_port_bundles(self):
      """
      Devuelve un dict[port_name, DataFrame] listo para ser consumido por
      LineUpExcelReport.
 
      El DataFrame de cada puerto estará:
        - Sin columnas auxiliares internas (prefijo '_')
        - Con tipos de datos compatibles con Excel (fechas como datetime,
          numéricos como float/int, el resto como str)
        - Filas inválidas/descartadas eliminadas
 
      TODO: implementar _prepare_for_excel() cuando se defina el contrato
            exacto de columnas y tipos por layout.
      """
      result : dict[str,PortBundle] = {}
      for port, bundle in self._bundles.items():
         result[port] = PortBundle(port,self._prepare_for_excel(bundle.df.copy(), bundle), bundle.report,bundle.layout)
         
      return result
   
   @staticmethod
   def _fill_na(df: pd.DataFrame) -> pd.DataFrame:
      """
      Rellena NAs con 'TBC' solo en columnas que lo aceptan (object/string).
      Columnas numéricas o de fecha se convierten primero a object para
      poder recibir 'TBC', ya que en Excel igual se escriben como string.
      """
      for col in df.columns:
         if df[col].isna().any():
            df[col] = df[col].astype(object).fillna('TBC')
      return df

   def _prepare_for_excel(self, df: pd.DataFrame, bundle: PortBundle) -> pd.DataFrame:
      """
      Limpia y convierte el DataFrame para escritura en Excel.
 
      TODO: implementar cuando se defina el contrato de columnas/tipos.
      """
      
      mask_skip = df[Columns.MT_BY_PRODUCT].isna() | df[Columns.MT_BY_PRODUCT].str.contains("/", na=False)
      
      df[Columns.MT_BY_PRODUCT] = np.where(
          mask_skip,
          df[Columns.MT_BY_PRODUCT],          # deja el valor original (string o NA)
          _to_decimal(df[Columns.MT_BY_PRODUCT])  # castea a Decimal
      )

      df[Columns.MT_BY_PRODUCT] = df[Columns.MT_BY_PRODUCT].astype(object).fillna('TBC')
      for date_col,period_col in [
         (Columns.DATE_OF_ARRIVAL,Columns.DATE_OF_ARRIVAL_PERIOD),
         (Columns.ETB,Columns.ETB_PERIOD),
         (Columns.ETC,Columns.ETC_PERIOD)
      ]:
         
         base = (
             df[date_col].dt.day.astype("Int64").astype('string').str.zfill(2)
             + " - "
             + df[date_col].dt.month.map(_MONTH_ABBR)
         )
         
         period = df[period_col].astype('string').str.replace("DatePeriod.", "", regex=False)         
         # Concatenar solo cuando haya periodo
         result = np.where(
             period.notna(),
             base + " " + period,
             base
         )
         
         # Manejar fechas nulas → "TBC"
         df[date_col] = np.where(
             df[date_col].notna(),
             result,
             "TBC"
         )

      
      col_name = Columns.PIER
      col = df[col_name]
      
      # Detectar los que tienen "/"
      has_slash = col.astype("string").str.contains("/", na=False)
      is_empty = col.isna()
      
      # Convertir columna a object (una sola vez)
      df[col_name] = df[col_name].astype(object)
      
      # Sin slash y no vacío → convertir a entero
      mask_number = ~has_slash & ~is_empty
      df.loc[mask_number, col_name] = col[mask_number].astype(int)
      
      # Vacíos → "TBC"
      df.loc[is_empty, col_name] = "TBC"      
      df = self._fill_na(df) 
      return df
   def _build_global_df(self) -> None:
      frames = [b.df for b in self._bundles.values()]
      if not frames:
         logger.warning("PostProcessor: no hay DataFrames para concatenar.")
         return
      self._df = pd.concat(frames, ignore_index=True)
      logger.info(
         "PostProcessor: DataFrame global construido — %d filas, %d puertos.",
         len(self._df),
         len(self._bundles),
      )

   def _check_overlaps(self) ->None:
      if self._df.empty:
         return
 
      conflicts: list[OverlapConflict] = check_overlaps(
         self._df, row_offset=self._row_offset
      )
 
      if not conflicts:
         logger.info("PostProcessor: sin solapamientos detectados.")
         return 
 
      logger.warning(
         "PostProcessor: se detectaron %d solapamiento(s).", len(conflicts)
      )
 
      for c in conflicts:
         logger.error(
            "SOLAPAMIENTO — barco '%s' | "
            "Fila A=%d (hoja='%s', intervalo=%s) vs "
            "Fila B=%d (hoja='%s', intervalo=%s) | "
            "Datos A=%s | Datos B=%s",
            c.vessel,
            c.row_a,
            c.sheet_a,
            c.interval_a,
            c.row_b,
            c.sheet_b,
            c.interval_b,
            c.row_a_data,
            c.row_b_data,
         )
      self._vessel_conflicts = conflicts

   def _run_company_matching(self) -> None:
      company_cfg = self._config.get("company_matching", {})
 
      role_idx = self._validation_data.get_companies_by_role(
         charterers=company_cfg.get("check_charterer", False),
         agencies=company_cfg.get("check_agency", False),
         owners=company_cfg.get("check_owner", False),
      )
 
      strategy = company_cfg.get("strategy", "global")
      scores_cfg = company_cfg.get("scores", {})
      max_suggestions: int = self._config.get("max_suggestions", 5)
 
      col_role_map = {
         Columns.CHARTERER: ("check_charterer", "charterers"),
         Columns.SHIPOWNER: ("check_owner", "owners"),
         Columns.AGENCY:    ("check_agency", "agencies"),
      }
 
      for col, (cfg_flag, role_key) in col_role_map.items():
         if not company_cfg.get(cfg_flag, False):
            continue
 
         exact_mask = self._df[col].isin(role_idx[role_key])
         unknown_series = (
            self._df[~exact_mask]
            .groupby(col)["PORT"]
            .agg(set)
         )
 
         if unknown_series.empty:
            logger.info(
               "Company matching [%s]: todas las empresas reconocidas.", role_key
            )
            continue
 
         logger.info(
            "Company matching [%s]: %d empresa(s) desconocida(s) para revisar.",
            role_key,
            len(unknown_series),
         )
 
         company_verse = (
            self._validation_data.get_all_companies()
            if strategy == "global"
            else role_idx[role_key]
         )
 
         for unknown_company, ports in unknown_series.items():
            assert isinstance(unknown_company, str)
 
            all_candidates = self._merge_fuzzy_results(
               unknown_company,
               company_verse,
               scores_cfg,
               max_suggestions,
             )
 
            if not all_candidates:
               logger.warning(
                  "Company matching [%s]: '%s' (puertos: %s) — "
                  "sin candidatos encontrados con los umbrales actuales.",
                  role_key,
                  unknown_company,
                  sorted(ports),
               )
               self._match_report["companies"].append(
                  {
                     "original": unknown_company,
                     "ports": sorted(ports),
                     "suggestions": {},
                     "searched_as": role_key,
                  }
               )
               continue
 
            suggestions = self._validation_data.get_company_roles(
               all_candidates.keys()
            )
 
            logger.info(
               "Company matching [%s]: '%s' (puertos: %s) — "
               "%d candidato(s): %s",
               role_key,
               unknown_company,
               sorted(ports),
               len(suggestions),
               [
                  f"{name} (shipowner={r.is_shipowner}, "
                  f"charterer={r.is_charterer}, agency={r.is_agency})"
                  for name, r in suggestions.items()
               ],
             )
 
            self._match_report["companies"].append(
               {
                  "original": unknown_company,
                  "ports": sorted(ports),
                  "suggestions": suggestions,
                  "searched_as": role_key,
               }
            )
 

   def _run_port_matching(self) -> None:
      if not self._config.get("port_matching", {}).get("enabled", False):
         return
 
      known_ports = self._validation_data.get_port_countries()
      scores_cfg = self._config.get("port_matching", {}).get("scores", {})
      max_suggestions: int = self._config.get("max_suggestions", 5)
 
      port_col = Columns.PORT_LOAD_DISCH
      exact_mask = self._df[port_col].isin(known_ports)
      unknown_series = (
         self._df[~exact_mask]
         .groupby(port_col)["PORT"]
         .agg(set)
      )
 
      if unknown_series.empty:
         logger.info("Port matching: todos los puertos reconocidos.")
         return
 
      logger.info(
         "Port matching: %d puerto(s) desconocido(s) para revisar.",
         len(unknown_series),
      )
 
      for unknown_port, ports in unknown_series.items():
         assert isinstance(unknown_port, str)
 
         all_candidates = self._merge_fuzzy_results(
            unknown_port, known_ports, scores_cfg, max_suggestions
         )
 
         if not all_candidates:
            logger.warning(
               "Port matching: '%s' (encontrado en: %s) — "
               "sin candidatos con los umbrales actuales.",
               unknown_port,
               sorted(ports),
            )
            self._match_report["ports"].append(
               {
                  "original": unknown_port,
                  "ports": sorted(ports),
                  "suggestions": [],
               }
            )
            continue
 
         suggestions = sorted(
            all_candidates.items(), key=lambda x: x[1], reverse=True
         )[:max_suggestions]
 
         logger.info(
            "Port matching: '%s' (encontrado en: %s) — "
            "%d candidato(s): %s",
            unknown_port,
            sorted(ports),
            len(suggestions),
            [f"{name} (score={score:.1f})" for name, score in suggestions],
         )
 
         self._match_report["ports"].append(
            {
               "original": unknown_port,
               "ports": sorted(ports),
               "suggestions": suggestions,
            }
         )
   def _run_vessel_matching(self) -> None:
      if not self._config.get("vessel_matching", {}).get("enabled", False):
         return
 
      known_vessels = self._validation_data.get_vessels()
      scores_cfg = self._config.get("vessel_matching", {}).get("scores", {})
      max_suggestions: int = self._config.get("max_suggestions", 5)
 
      vessel_col = Columns.VESSEL
      exact_mask = self._df[vessel_col].isin(known_vessels)
      unknown_series = (
         self._df[~exact_mask]
         .groupby(vessel_col)["PORT"]
         .agg(set)
      )
 
      if unknown_series.empty:
         logger.info("Vessel matching: todos los barcos reconocidos.")
         return
 
      logger.info(
         "Vessel matching: %d barco(s) desconocido(s) para revisar.",
         len(unknown_series),
      )
 
      for unknown_vessel, ports in unknown_series.items():
         assert isinstance(unknown_vessel, str)
 
         all_candidates = self._merge_fuzzy_results(
            unknown_vessel, known_vessels, scores_cfg, max_suggestions
         )
 
         if not all_candidates:
            logger.warning(
               "Vessel matching: '%s' (encontrado en: %s) — "
               "sin candidatos con los umbrales actuales.",
               unknown_vessel,
               sorted(ports),
            )
            self._match_report["vessels"].append(
               {
                  "original": unknown_vessel,
                  "ports": sorted(ports),
                  "suggestions": [],
               }
            )
            continue
 
         suggestions = sorted(
            all_candidates.items(), key=lambda x: x[1], reverse=True
         )[:max_suggestions]
 
         logger.info(
            "Vessel matching: '%s' (encontrado en: %s) — "
            "%d candidato(s): %s",
            unknown_vessel,
            sorted(ports),
            len(suggestions),
            [f"{name} (score={score:.1f})" for name, score in suggestions],
         )
 
         self._match_report["vessels"].append(
            {
               "original": unknown_vessel,
               "ports": sorted(ports),
               "suggestions": suggestions,
            }
         )

   
   @staticmethod
   def _merge_fuzzy_results(
       query: str,
       choices: list[str] | set[str],
       scores_cfg: dict,
       limit: int,
   ) -> dict[str, float]:
      """
      Corre los tres scorers de rapidfuzz y une los resultados tomando
      el mejor score por candidato.
      Retorna dict[candidato -> mejor_score], ordenado desc, limitado a `limit`.
      """
      simple  = process.extract(query, choices, scorer=fuzz.ratio,          score_cutoff=scores_cfg.get("simple_ratio",   80), limit=limit)
      partial = process.extract(query, choices, scorer=fuzz.partial_ratio,   score_cutoff=scores_cfg.get("partial_ratio",  80), limit=limit)
      token   = process.extract(query, choices, scorer=fuzz.token_set_ratio, score_cutoff=scores_cfg.get("token_set_ratio",80), limit=limit)
 
      merged: dict[str, float] = {}
      for match_list in (simple, partial, token):
         for match, score, _ in match_list:
            if match not in merged or score > merged[match]:
               merged[match] = score
 
      return dict(
         sorted(merged.items(), key=lambda x: x[1], reverse=True)[:limit]
      )
   @property
   def get_vessel_overlaps(self):
      return self._vessel_conflicts

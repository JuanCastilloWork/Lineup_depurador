from enum import Enum
import enums
from excel.layots import *
from excel import has_valid_headers
from abc import ABC,abstractmethod
from typing import TYPE_CHECKING, Generic
from excel.layots import Columns
from validations import ValidationReport
from decimal import Decimal
from .utils import _to_decimal
import logging
import numpy as np
import pandas as pd
from sys import maxsize
import re
from datetime import datetime

from validations.error_registry import ErrorType, WarningLevel, WarningType
if TYPE_CHECKING:
   import openpyxl
   from additional_data import LineUpValidationsData

logger = logging.getLogger(__name__)

_OPEN_END = maxsize

SEP = re.compile(r'[\/\-\+;]')
MAX_MT = Decimal("300000")
MARGIN_THRESHOLD = Decimal("0.20")

_SAILED_PRODUCT_EXEMPT = {
   enums.CargoType.STEEL.value: enums.CargoType.STEEL.value,
   enums.CargoType.FERTILIZERS.value:enums.CargoType.FERTILIZERS.value,
   enums.CargoType.PROJECT_CARGO.value:'GENERAL CARGO',
}

_SAILED_CHARTERER_EXEMPT = {
   enums.CargoType.STEEL.value,
   enums.CargoType.FERTILIZERS.value,
   enums.CargoType.CLINKER_CEMENT.value,
   enums.CargoType.LIQUID_CHEMS.value,
   enums.CargoType.CRUDE.value
}

_VALID_STATUS_OPERATIONS = {
   enums.VesselStatus.ANNOUNCED:    {enums.OperationStatus.TO_DISCHARGE, enums.OperationStatus.TO_LOAD},
   enums.VesselStatus.AT_LOAD_PORT: {enums.OperationStatus.TO_DISCHARGE, enums.OperationStatus.TO_LOAD, enums.OperationStatus.TO_REPAIR},
   enums.VesselStatus.DRIFTING:     {enums.OperationStatus.TO_REPAIR, enums.OperationStatus.TOWING},
   enums.VesselStatus.SAILED:       {enums.OperationStatus.LOADED, enums.OperationStatus.DISCHARGED},
   enums.VesselStatus.BERTHED: {
      enums.OperationStatus.DISCHARGING,
      enums.OperationStatus.DISCHARGED,
      enums.OperationStatus.LOADING,
      enums.OperationStatus.LOADED,
      enums.OperationStatus.TO_REPAIR,
   },
   enums.VesselStatus.ANCHORED : {enums.OperationStatus.TO_DISCHARGE,enums.OperationStatus.TO_LOAD}
}

def _validate_status(
   df : pd.DataFrame,
   col_vessel_status: str,
   col_operation_status: str,
   col_etb: str,
   col_etc: str,
   col_ata: str,
   col_type: str,
   col_product: str,
   col_mt_by_product: str,
   col_total_mt: str,
   col_shipowner: str,
   col_charterer: str,
   col_agency: str,
   col_vessel: str,
   blacklist: set[str],
   report: ValidationReport,
   current_date : datetime
)->pd.DataFrame:
   """
   Funcion Helper para validar los estados, es algo que se deberia de hacer de ultimas, y deberia de preguntar por varias cosas 
   """

   bad_status_idx = set(report.idx_errors_by_column(col_vessel_status))
   bad_op_idx     = set(report.idx_errors_by_column(col_operation_status))
   bad_ata_idx    = set(report.idx_errors_by_column(col_ata))
   bad_etb_idx    = set(report.idx_errors_by_column(col_etb))
   bad_etc_idx    = set(report.idx_errors_by_column(col_etc))   
   
   vs = df[col_vessel_status]
   ops = df[col_operation_status]

   bad_status_idx  = set(report.idx_errors_by_column(col_vessel_status))
   bad_op_idx      = set(report.idx_errors_by_column(col_operation_status))

   
   def add_err(idx, col, val, reason, etype):
      report.add_error(df.at[idx, col_vessel], int(idx), col, val, reason, etype)
      logger.error("Indice %s | %s | %s | %s", idx, col, val, reason)

   # ── 1. BERTHED requiere ETB ───────────────────────────────────────────
   # Si la ETB no se pudo convertir, va a ser vacia, quitamos los vacios por errores de conversion
   m_berthed = vs == enums.VesselStatus.BERTHED.value
   m_etb_missing = m_berthed & df[col_etb].isna()& ~df.index.isin(bad_etb_idx)
   for idx, val in df.loc[m_etb_missing, col_etb].items():
      add_err(idx, col_etb, val,
      f"Status '{enums.VesselStatus.BERTHED.value}' requiere ETB",
      ErrorType.MISSING_VALUE)

   # ── 2. SAILED requiere ETC ────────────────────────────────────────────
   # Si la ETC no se pudo convertir, va a ser vacia, quitamos los vacios por errores de conversion
   m_sailed = vs == enums.VesselStatus.SAILED.value
   m_etc_missing = m_sailed & df[col_etc].isna() & ~ df.index.isin(bad_etc_idx)
   for idx, val in df.loc[m_etc_missing, col_etc].items():
      add_err(idx, col_etc, val,
      f"Status '{enums.VesselStatus.SAILED.value}' requiere ETC",
      ErrorType.MISSING_VALUE)

   # ── 3. SAILED requiere ETA ────────────────────────────────────────────
   # Si la ETC no se pudo convertir, va a ser vacia, quitamos los vacios por errores de conversion
   m_ata_missing = m_sailed & df[col_ata].isna() & ~df.index.isin(bad_ata_idx)
   for idx, val in df.loc[m_ata_missing, col_ata].items():
      add_err(idx, col_ata, val,
      f"Status '{enums.VesselStatus.SAILED.value}' requiere ETA",
      ErrorType.MISSING_VALUE)   

   # ── 4. Validaciones cronológicas por estado ───────────────────────────
   #
   # La columna de fecha puede haber fallado en conversión O en intervalo;
   # en ambos casos ya hay un error en el report → la excluimos con bad_*_idx.
   # Solo validamos filas donde el status es válido (no en bad_status_idx).
   
   valid_status = ~df.index.isin(bad_status_idx)   
   
   # 4a. ANNOUNCED → ETA debe ser >= current_date si existe
   m_announced = valid_status & (vs == enums.VesselStatus.ANNOUNCED.value)
   m_ata_past  = m_announced & df[col_ata].notna() & ~df.index.isin(bad_ata_idx) & (df[col_ata] < current_date)
   for idx, val in df.loc[m_ata_past, col_ata].items():
      add_err(idx, col_ata, val,
         f"Status '{enums.VesselStatus.ANNOUNCED.value}': ETA ya pasó "
         f"(debería ser ANCHORED/DRIFTING/BERTHED)",
         ErrorType.OUT_OF_RANGE) 

   # 4b. ANCHORED / DRIFTING → ETA debe ser <= current_date
   m_anch_drift = valid_status & vs.isin([
      enums.VesselStatus.ANCHORED.value,
      enums.VesselStatus.DRIFTING.value,
   ])
   m_ata_future = m_anch_drift & df[col_ata].notna() & ~df.index.isin(bad_ata_idx) & (df[col_ata] > current_date)
   #m_ata_future = m_anch_drift & ~df.index.isin(bad_ata_idx) & ((df[col_ata] > current_date) | df[col_ata].isna())
   for idx, val in df.loc[m_ata_future, col_ata].items():
      add_err(idx, col_ata, val,
         f"Status '{vs.at[idx]}': ETA no puede ser futura o vacia",
         ErrorType.OUT_OF_RANGE)

   # ETB en ANCHORED/DRIFTING: si existe y es < current_date → inconsistencia
   m_etb_past_anch = (
      m_anch_drift
      & df[col_etb].notna()
      & ~df.index.isin(bad_etb_idx)
      & (df[col_etb] < current_date)
   )
   for idx, val in df.loc[m_etb_past_anch, col_etb].items():
      add_err(idx, col_etb, val,
         f"Status '{vs.at[idx]}': ETB ya pasó, el barco debería estar BERTHED",
         ErrorType.OUT_OF_RANGE)

   # 4c. BERTHED → ETB debe ser <= current_date
   m_etb_future_berthed = (
      m_berthed & valid_status
      & df[col_etb].notna()
      & ~df.index.isin(bad_etb_idx)
      & (df[col_etb] > current_date)
   )
   for idx, val in df.loc[m_etb_future_berthed, col_etb].items():
      add_err(idx, col_etb, val,
         f"Status '{enums.VesselStatus.BERTHED.value}': ETB no puede ser futura",
         ErrorType.OUT_OF_RANGE)

   # ETC en BERTHED: si existe y es < current_date → debería ser SAILED
   m_etc_past_berthed = (
      m_berthed & valid_status
      & df[col_etc].notna()
      & ~df.index.isin(bad_etc_idx)
      & (df[col_etc] < current_date)
   )
   for idx, val in df.loc[m_etc_past_berthed, col_etc].items():
      add_err(idx, col_etc, val,
         f"Status '{enums.VesselStatus.BERTHED.value}': ETC ya pasó, "
         f"el barco debería estar SAILED",
         ErrorType.OUT_OF_RANGE)

   # 4d. SAILED → ETC debe ser <= current_date
   m_etc_future_sailed = (
      m_sailed & valid_status
      & df[col_etc].notna()
      & ~df.index.isin(bad_etc_idx)
      & (df[col_etc] > current_date)
   )
   for idx, val in df.loc[m_etc_future_sailed, col_etc].items():
      add_err(idx, col_etc, val,
         f"Status '{enums.VesselStatus.SAILED.value}': ETC no puede ser futura",
         ErrorType.OUT_OF_RANGE)  

   # ── 5. Vessel status vs Operation status ─────────────────────────────
   # Puede pasar que vessel estadus y Operation estatus tengan errores de conversion, por lo que hay que capturar los errores de cualquiera de las dos columnas

   skip_idx = bad_status_idx | bad_op_idx   
   both_present = vs.notna() & ops.notna() &~df.index.isin(skip_idx)
   for row in df.loc[both_present].itertuples():
      idx = int(row.Index)
      v_status = getattr(row, col_vessel_status)
      o_status = getattr(row, col_operation_status)
      allowed_ops = _VALID_STATUS_OPERATIONS.get(v_status, set())
      if o_status not in allowed_ops:
         reason = (
            f"OperationStatus '{o_status.value}' no es válido "
            f"para VesselStatus '{v_status.value}'"
         )
         report.add_error(df.at[idx, col_vessel], idx, col_operation_status, o_status, reason, ErrorType.INVALID_VALUE)
         logger.error('Indice %s | %s | %s | %s', idx, col_operation_status, o_status, reason)

   # ── 6. SAILED: excepciones y check de nulos ───────────────────────────
   
   def _is_exempt(row) -> bool:
      cargo_type = getattr(row, col_type)
      exc_cargo  = cargo_type in _SAILED_PRODUCT_EXEMPT
      exc_company = any(
         str(getattr(row, col)).upper() in blacklist
         for col in (col_shipowner, col_charterer, col_agency)
         if not pd.isna(getattr(row, col))
      )
      return exc_cargo or exc_company

   for row in df.loc[m_sailed].itertuples():
      idx = int(row.Index)
      exempt = _is_exempt(row)
      
      if exempt:
         if pd.isna(getattr(row, col_product)):
            df.at[idx, col_product] = _SAILED_PRODUCT_EXEMPT[getattr(row, col_type)]
            
         if pd.isna(getattr(row, col_mt_by_product)):
            df.at[idx, col_mt_by_product] = getattr(row, col_total_mt)

      # check nulos sobre todas las columnas a no ser que esas columnas ya hayan sido reportadas por otro error
      for col in df.columns:
         
         if idx in report.idx_errors_by_column(col):
            continue
         val = df.at[idx, col]
         if pd.isna(val):
            _status = df.at[idx,col_type]
            if col == col_charterer and pd.notna(_status) and _status in _SAILED_CHARTERER_EXEMPT:
               reason = f"'{col}' es nulo y el Status es sailed, se deja el nulo ya que el {col_type} hace parte de las excepciones de charteadores"
               report.add_warning(df.at[idx, col_vessel], idx, col, val, reason, WarningLevel.MEDIUM,WarningType.MISSING_OPTIONAL)
               logger.warning('Indice %s | %s | %s | %s', idx, col, val, reason)
               continue
            reason = f"Status SAILED requiere valor en todas las columnas — '{col}' es nulo"
            report.add_error(df.at[idx, col_vessel], idx, col, val, reason, ErrorType.MISSING_VALUE)
            logger.error('Indice %s | %s | %s | %s', idx, col, val, reason)

   return df

def _validate_cargo(
   df: pd.DataFrame,
   col_type: str,
   col_product: str,
   col_mt_by_product: str,
   col_total_mt: str,
   col_vessel: str,
   valid_products: pd.DataFrame,
   report: ValidationReport,
) -> pd.DataFrame:

   invalid: dict[int, list[str]] = {}

   def mark(idx: int, *cols: str):
      invalid.setdefault(idx, []).extend(cols)

   # ── Masks base ────────────────────────────────────────────────────────
   type_na  = df[col_type].isna()
   prod_na  = df[col_product].isna()
   mt_bp_na = df[col_mt_by_product].isna()
   total_na = df[col_total_mt].isna()

   # ── 1. TYPE NA + PRODUCT no NA ────────────────────────────────────────
   # Si col_type tuvo un problmea de conversion a enum, va a tener el valor como None, y puede matchear aqui, cosa que seria incorrecto por que si pusieron algo
   bad_type_idx = set(report.idx_errors_by_column(col_type))
   m1 = type_na & ~prod_na & ~df.index.isin(bad_type_idx)
   for idx, val in df.loc[m1, col_product].items():
      reason = f"PRODUCT '{val}' existe sin un TYPE válido"
      report.add_error(df.at[idx, col_vessel], int(idx), col_product, val, reason, ErrorType.MISSING_VALUE)
      logger.error('Indice %s | %s | %s | %s', idx, col_product, val, reason)
      mark(int(idx), col_product)

   # ── 2. NA cruzado TOTAL_MT / MT_BY_PRODUCT ────────────────────────────
   # Nosotros tenemos definidos que mt_bp es tipo texto, por lo que no deberia de haber problema en el casteo de esa columna, pero total_na si puede tener problemas

   bad_total_idx  = set(report.idx_errors_by_column(col_total_mt))
   m2_a = ~mt_bp_na &  total_na & ~df.index.isin(bad_total_idx)  # tiene mt_by pero no total
   #m2_b =  mt_bp_na & ~total_na   # tiene total pero no mt_by
   for mask, missing, present in [
      (m2_a, col_total_mt,      col_mt_by_product),
   #   (m2_b, col_mt_by_product, col_total_mt),
   ]:
      for idx, val in df.loc[mask, missing].items():
         reason = f"'{missing}' es NA pero '{present}' tiene valor"
         report.add_error(df.at[idx, col_vessel], int(idx), missing, val, reason, ErrorType.MISSING_VALUE)
         logger.error('Indice %s | %s | %s | %s', idx, missing, val, reason)
         mark(int(idx), missing)

   # ── Separamos en base a los separadores → listas ──────────────────────
   prod_lists = df[col_product].str.split(SEP)       # NaN → NaN
   mt_lists   = df[col_mt_by_product].str.split(SEP)

   # ── 3. Conteo de partes desigual ──────────────────────────────────────
   # En esta parte ya garantizamos que da igual los problemas de conversion por que quitamos los nas de ambos lados
   both_present = ~prod_na & ~mt_bp_na
   count_mismatch = both_present & (
      prod_lists.str.len() != mt_lists.str.len()
   )
   for idx, prod, mt in df.loc[count_mismatch, [col_product, col_mt_by_product]].itertuples():
      reason = (
         f"Cantidad de productos ({len(SEP.split(str(prod)))}) "
         f"no coincide con MT_BY_PRODUCT ({len(SEP.split(str(mt)))})"
      )
      report.add_warning(df.at[idx, col_vessel], int(idx), col_mt_by_product, mt, reason,WarningLevel.HIGH,WarningType.SUSPICIOUS_VALUE)
      logger.error('Indice %s | %s | %s | %s', idx, col_mt_by_product, mt, reason )
      # mark(int(idx), col_product, col_mt_by_product)  

   # ── 4. TOTAL_MT rango ─────────────────────────────────────────────────
   # Si total_mt tuvo un problema de casteo, el valor va a quedar como NA
   total_dec_series = df[col_total_mt]

   out_of_range_total = ~total_na & total_dec_series.apply(
      lambda d: pd.isna(d) or not (Decimal("0") < d < MAX_MT)
   )
   for idx, val in df.loc[out_of_range_total, col_total_mt].items():
      reason = f"TOTAL_MT '{val}' fuera de rango (0, 300 000)"
      report.add_error(df.at[idx, col_vessel], int(idx), col_total_mt, val, reason,ErrorType.INVALID_VALUE)
      logger.error('Indice %s | %s | %s | %s', idx, col_total_mt, val, reason, )
      mark(int(idx), col_total_mt)

   # 4.1 TOTAL_MT vs una unica cantidad en mt_by_product

   single_mt_multi_prod = (
      both_present
      & (mt_lists.str.len() == 1)
      & (prod_lists.str.len() > 1)
   )
   bad_total_idx_set = set(report.idx_errors_by_column(col_total_mt))
   
   for idx, row in df.loc[single_mt_multi_prod, [col_mt_by_product, col_total_mt, col_vessel]].iterrows():
      mt_val_raw  = mt_lists.at[idx][0].strip()
      total_val   = total_dec_series.at[idx]
   
      # Si total_mt tuvo error de casteo no podemos comparar
      if int(idx) in bad_total_idx_set or pd.isna(total_val):
         continue
   
      mt_dec = _to_decimal([mt_val_raw])
      if mt_dec[0] is None:
         continue  # ya será capturado en sección 5 cuando se explote
   
      if mt_dec[0] != total_val:
         diff = abs(mt_dec[0] - total_val)
         reason = (
            f"MT_BY_PRODUCT tiene un solo valor ({mt_dec[0]}) para {prod_lists.at[idx].__len__()} productos "
            f"pero difiere de TOTAL_MT ({total_val}) — diferencia: {diff}"
         )
         report.add_warning(
            row[col_vessel], int(idx), col_mt_by_product,
            row[col_mt_by_product], reason,
            WarningLevel.HIGH, WarningType.SUSPICIOUS_VALUE
         )
         logger.warning('Indice %s | %s | %s | %s', idx, col_mt_by_product, row[col_mt_by_product], reason)
   # ── Explode ───────────────────────────────────────────────────────────
   # Solo filas donde ambas listas existen
   #explodable = both_present
   explodable = both_present & ~count_mismatch
   df_exp = (
      df.loc[explodable, [col_type, col_product, col_mt_by_product]]
      .assign(**{
          col_product:       prod_lists,
          col_mt_by_product: mt_lists,
      })
      #.explode([col_product, col_mt_by_product])
      .explode([col_product, col_mt_by_product])
   )
   df_exp[col_product]       = df_exp[col_product].str.strip().str.upper()
   df_exp[col_mt_by_product] = df_exp[col_mt_by_product].str.strip()

   # ── 5. Casteo a Decimal + rango por elemento ──────────────────────────
   # Aqui es safe no hacer nada por que son errores nuevos
   df_exp['_mt_dec'] = _to_decimal(df_exp[col_mt_by_product].to_numpy())

   invalid_dec = df_exp['_mt_dec'].isna() & df_exp[col_mt_by_product].notna()
   for idx in df_exp.loc[invalid_dec].index.unique():
      val = df.at[idx, col_mt_by_product]
      reason = f"MT_BY_PRODUCT '{val}' contiene valores no decimales"
      report.add_error(df.at[idx, col_vessel], int(idx), col_mt_by_product, val, reason, ErrorType.INVALID_VALUE)
      logger.error('Indice %s | %s | %s | %s', idx, col_mt_by_product, val, reason)
      mark(int(idx), col_mt_by_product)

   out_of_range_mt = df_exp['_mt_dec'].apply(
      lambda d: not pd.isna(d) and not (Decimal("0") < d < MAX_MT)
   )
   for idx in df_exp.loc[out_of_range_mt].index.unique():
      val = df.at[idx, col_mt_by_product]
      reason = f"MT_BY_PRODUCT '{val}' contiene valores fuera de rango (0, 300 000)"
      report.add_error(df.at[idx, col_vessel], int(idx), col_mt_by_product, val, reason, ErrorType.INVALID_VALUE)
      logger.error('Indice %s | %s | %s | %s', idx, col_mt_by_product, val, reason)
      mark(int(idx), col_mt_by_product)

   # ── 6. Suma por grupo == TOTAL_MT ─────────────────────────────────────
   # Si de casualida hubo un error en el casteo de mt_total, hay que quitarlo
   bad_mt_idx   = df_exp.loc[invalid_dec | out_of_range_mt].index.unique()
   bad_total_idx = df.loc[out_of_range_total].index
   skip_sum_idx  = bad_mt_idx.union(bad_total_idx)

   df_exp_sum = df_exp.loc[~df_exp.index.isin(skip_sum_idx) & ~df_exp.index.isin(bad_total_idx)]
   mt_sums = df_exp_sum.groupby(level=0)['_mt_dec'].apply(
      lambda s: sum(v for v in s if not pd.isna(v))
   )
   for idx, mt_sum in mt_sums.items():
      total = total_dec_series.at[idx]
      if pd.isna(total) or mt_sum == total:
         continue
       
      diff_ratio = abs(mt_sum - total) / total
      if diff_ratio <= MARGIN_THRESHOLD:
         reason = (
             f"Suma MT_BY_PRODUCT ({mt_sum}) difiere de TOTAL_MT ({total}) "
             f"— margen {float(diff_ratio):.1%} (≤20%)"
         )
         report.add_error(df.at[idx, col_vessel], int(idx), col_mt_by_product, df.at[idx, col_mt_by_product], reason, ErrorType.INVALID_VALUE)
         logger.error('Indice %s | %s | %s | %s', idx, col_mt_by_product, str(df.at[idx, col_mt_by_product]), reason)
         mark(int(idx), col_mt_by_product)
      else:
         reason = (
             f"Suma MT_BY_PRODUCT ({mt_sum}) difiere de TOTAL_MT ({total}) "
             f"— margen {float(diff_ratio):.1%} (>20%)"
         )
         report.add_error(df.at[idx, col_vessel], int(idx), col_mt_by_product, df.at[idx, col_mt_by_product], reason, ErrorType.INVALID_VALUE)
         report.add_error(df.at[idx, col_vessel], int(idx), col_total_mt, df.at[idx, col_total_mt], reason, ErrorType.INVALID_VALUE)
         logger.error('Indice %s | %s | %s | %s', idx, col_mt_by_product, df.at[idx, col_mt_by_product], reason)
         mark(int(idx), col_mt_by_product, col_total_mt)

   # ── 7. Validar productos vs dict (sobre df_exp) ───────────────────────
   # Tenemos que quitar los productos que hayan tenido problemas de NA de conversion
   allowed_map = (
      valid_products.groupby(level=0)["NAME"]
      .apply(lambda s: set(s.str.upper().dropna()))
      .to_dict()
   )
   bad_type_idx = set(report.idx_errors_by_column(col_type))
   valid_exp = df_exp.loc[~type_na.reindex(df_exp.index, fill_value=False) & ~df_exp.index.isin(bad_type_idx) ].copy()
   valid_exp["_cargo_type"] = df.loc[valid_exp.index, col_type]
   valid_exp["_allowed"] = [
      val in allowed_map.get(ct, set())
      for val, ct in zip(valid_exp[col_product], valid_exp["_cargo_type"])
   ]
   
   bad = valid_exp.loc[~valid_exp["_allowed"]]
   
   for idx in bad.index.unique():
      original_val = df.at[idx, col_product]
      cargo_type   = df.at[idx, col_type]
      product      = bad.at[idx, col_product]  # puede ser Series si hay múltiples
      products = product.tolist() if isinstance(product, pd.Series) else [product]
      for p in products:
         reason = f"Producto '{p}' no es válido para el tipo '{cargo_type}'"
         report.add_warning(df.at[idx, col_vessel], idx, col_product, original_val, reason, WarningLevel.MEDIUM, WarningType.SUSPICIOUS_VALUE)
         logger.warning('Indice %s | %s | %s | %s', idx, col_product, p, reason)
   
   # ── Reemplazar inválidos + formatear válidos ───────────────────────────
   for idx, cols in invalid.items():
      for col in set(cols):
         df.at[idx, col] = None
   
   valid_rows = explodable & ~pd.Series(df.index.isin(invalid), index=df.index)
   df.loc[valid_rows, col_product] = (
      prod_lists.loc[valid_rows].str.join("/")
   )
   df.loc[valid_rows, col_mt_by_product] = (
      df_exp.loc[~df_exp.index.isin(invalid)]
      .groupby(level=0)['_mt_dec']
      .apply(join_or_decimal)
   )

   mt_bp_empty = df[col_mt_by_product].isna()
   total_present = ~df[col_total_mt].isna()
   fallback_mask = mt_bp_empty & total_present

   if fallback_mask.any():
      df.loc[fallback_mask, col_mt_by_product] = df.loc[fallback_mask, col_total_mt].astype(str)
      for idx in df.loc[fallback_mask].index:
         logger.warning(
            'Indice %s | %s asumido desde %s | valor: %s',
            idx, col_mt_by_product, col_total_mt, df.at[idx, col_mt_by_product]
         )

   return df

def join_or_decimal(series):
   vals = series.dropna().tolist()
   
   if len(vals) == 1:
      return str(Decimal(vals[0]))
   elif len(vals) > 1:
       return "/".join(f'{v:,}' for v in vals)
   else:
       return None

def _format_port_country(series: pd.Series, colname: str, vessel_series: pd.Series, report: ValidationReport) -> pd.Series:
   original_na = series.isna()
   
   def parse_port(value):
      if pd.isna(value) or str(value).strip() == '':
         return value
      
      parts = re.split(r'[\/\-\+,]', str(value))
      
      if len(parts) == 2:
         port = parts[0].strip()
         country = parts[1].strip()
         return f"{port}, {country}"
      
      return None  # No se encontró separador → error
   
   parsed = series.map(parse_port)
   
   new_errors = parsed.isna() & ~original_na
   error_values = series[new_errors]
   assert isinstance(error_values, pd.Series)
   
   if error_values.empty:
      return parsed
   
   for idx, value in error_values.items():
      assert isinstance(idx,int)
      reason = f"Valor '{value}' no contiene un separador válido ('/', '-', '+', ',') para identificar puerto y país"
      report.add_error(vessel_series.at[idx], idx, colname, value, reason,ErrorType.INVALID_FORMAT)
      logger.error('Indice %s | %s | %s | %s', idx, colname, value, reason)
   
   return parsed


def _validate_terminals(series: pd.Series, colname: str, vessel_series: pd.Series, terminals: list, report: ValidationReport) -> pd.Series:
   original_na = series.isna()
   
   validated = series.where(series.isin(terminals), other=None)
   
   new_errors = validated.isna() & ~original_na
   error_values = series[new_errors]
   assert isinstance(error_values, pd.Series)
   
   if error_values.empty:
      return series
   
   for idx, value in error_values.items():
      assert isinstance(idx,int)
      reason = f"Valor '{value}' no es una terminal válida"
      report.add_error(vessel_series.at[idx], idx, colname, value, reason,ErrorType.INVALID_VALUE)
      logger.error('Indice %s | %s | %s | %s', idx, colname, value, reason)
   
   return series


def _cast_string(series : pd.Series)->pd.Series:
   result =  (series.astype('string').str.upper().apply(lambda v : re.sub(r'\s+'," ",v).strip() if isinstance(v,str) else v ).where(series.notna(),other = pd.NA))
   
   return result

def _cast_datetime(series : pd.Series, colname : str, vessel_series: pd.Series, report : ValidationReport)->pd.Series:
   """
   Funcion que crea los errores de tipo fecha para la conversion, no tiene dependencias y los errores quedan registrados en el registro 
   """
   original_na = series.isna()
   parsed = pd.to_datetime(series,format="%d/%m/%Y", errors="coerce")
   new_errors = parsed.isna() & ~original_na
   error_values : pd.Series = series.iloc[new_errors]

   assert isinstance(error_values,pd.Series)
   
   if error_values.empty:
      return parsed
   for idx, value in error_values.items():
      assert isinstance(idx,int)
      reason = f"Valor '{value}' no es una fecha válida (formato esperado: DD/MM/YYYY)"
      report.add_error(vessel_series.at[idx], idx, colname, value, reason, ErrorType.INVALID_VALUE)
      logger.error('Indice %s | %s | %s | %s', idx, colname, value, reason)
   
   return parsed

def _cast_et_interval(
   eta: pd.Series, eta_p: pd.Series,
   etb: pd.Series, etb_p: pd.Series,
   etc: pd.Series, etc_p: pd.Series,
   col_eta: str, col_eta_p: str,
   col_etb: str, col_etb_p: str,
   col_etc: str, col_etc_p: str,
   vessel_series: pd.Series,
   report: ValidationReport
) -> tuple[pd.Series, pd.Series]:
   """
   Esta funcion valida intervalos de fechas (eta<etb<etc) con los periodos correspondientes...
   Eso es problematico, teniendo en cuenta que todas pueden tener problemas de parseo (tanto los periodos como las fechas) 
   """

   def _to_ordinal(date_s: pd.Series, period_s: pd.Series, open_end: bool = False) -> pd.Series:
      result = pd.Series(pd.NA, index=date_s.index, dtype="Int64")
   
      fecha_nula = date_s.isna()
      mascara = ~fecha_nula
      a = period_s[mascara]
      assert isinstance(a,pd.Series)
      pm_mask = a.map(lambda p: p == enums.DatePeriod.PM.value if pd.notna(p) else open_end)

      b = date_s[mascara]
      assert isinstance(b,pd.Series)
      
      result[mascara] = (
         b.map(lambda f: f.toordinal()) * 2
         + pm_mask.astype(int)
      )
   
      if open_end:
         result[fecha_nula] = _OPEN_END
   
      return result

   def _report_error(idx, colname, value, reason, error_type):
      report.add_error(vessel_series.at[idx], int(idx), colname, value, reason,error_type)
      logger.error("Indice %s | %s | %s | %s", idx, colname, value, reason)

   eta_nula  = eta.isna()
   etb_nula  = etb.isna()
   etc_nula  = etc.isna()
   eta_p_nula = eta_p.isna()
   etb_p_nula = etb_p.isna()
   etc_p_nula = etc_p.isna()

   bad_eta_idx = set(report.idx_errors_by_column(col_eta))
   bad_etb_idx = set(report.idx_errors_by_column(col_etb))
   bad_etc_idx = set(report.idx_errors_by_column(col_etc))   

   # Regla 1: periodo presente pero su fecha ausente
   # EL PERIODO PUEDE TENER ERRORES DE CONVERSION, y termicamente si habria un periodo
   for fecha_nula, idx_malo, p_nula, p_series, col_fecha, col_p in [
      (eta_nula,bad_eta_idx, eta_p_nula, eta_p, col_eta, col_eta_p),
      (etb_nula,bad_etb_idx, etb_p_nula, etb_p, col_etb, col_etb_p),
      (etc_nula,bad_etc_idx, etc_p_nula, etc_p, col_etc, col_etc_p),
   ]:
      for idx, value in p_series[~p_nula & fecha_nula].items():# type: ignore
         if idx in idx_malo:
            continue
         _report_error(idx, col_p, value, f"Periodo '{value}' definido pero '{col_fecha}' está vacía",ErrorType.MISSING_VALUE)

   # Regla 2 y 3: dependencia entre fechas (eta es prerequisito de todo)
   for fecha_nula, f_series, col_f in [
       (etb_nula, etb, col_etb),
       (etc_nula, etc, col_etc),
   ]:
      for idx, value in f_series[eta_nula & ~fecha_nula].items():#type: ignore
         if idx in bad_eta_idx:
            continue    
         _report_error(idx, col_f, value, f"'{col_f}' presente pero '{col_eta}' está vacía",ErrorType.MISSING_VALUE)

   # Calcular ordinales solo en filas sin errores para eta y etc
   filas_con_error = (
       (~eta_p_nula & eta_nula) |
       (~etb_p_nula & etb_nula) |
       (~etc_p_nula & etc_nula) |
       (eta_nula & ~etb_nula)   |
       (eta_nula & ~etc_nula)
   )

   eta_clean = eta.copy()
   etb_clean = etb.copy()
   etc_clean = etc.copy()
   eta_p_clean = eta_p.copy()
   etb_p_clean = etb_p.copy()
   etc_p_clean = etc_p.copy()

   eta_clean[filas_con_error] = pd.NaT
   etb_clean[filas_con_error] = pd.NaT
   etc_clean[filas_con_error] = pd.NaT
   eta_p_clean[filas_con_error] = None
   etb_p_clean[filas_con_error] = None
   etc_p_clean[filas_con_error] = None

   eta_ord_raw = _to_ordinal(eta, eta_p)
   etb_ord_raw = _to_ordinal(etb, etb_p)
   etc_ord_raw = _to_ordinal(etc, etc_p, True)   

   mask_valid = (
       eta_ord_raw.notna() &
       etb_ord_raw.notna() &
       etc_ord_raw.notna()
   )
   
   mask_bad_order = mask_valid & ~(
       (eta_ord_raw <= etb_ord_raw) &
       (etb_ord_raw <= etc_ord_raw)
   )
   for idx in eta.index[mask_bad_order]:
      e1 = eta_ord_raw.at[idx]
      e2 = etb_ord_raw.at[idx]
      e3 = etc_ord_raw.at[idx]

      c1 = e1 <= e2  # eta <= etb 
      c2 = e2 <= e3  # etb <= etc
      c3 = e1 <= e3  # eta <= etc

      # CASO 1: totalmente invertido
      if not c1 and not c2:
         _report_error(idx, col_eta, eta.at[idx], "ETA > ETB > ETC", ErrorType.OUT_OF_RANGE)
         _report_error(idx, col_etb, etb.at[idx], "ETA > ETB > ETC", ErrorType.OUT_OF_RANGE)
         _report_error(idx, col_etc, etc.at[idx], "ETA > ETB > ETC", ErrorType.OUT_OF_RANGE)

         eta_ord_raw.at[idx] = pd.NA
         etc_ord_raw.at[idx] = _OPEN_END

         continue

      if not c1:
         # eta> etb
         if not c3:
            # eta >etc
            # inconsistencia fuerte → matar todo
            _report_error(idx, col_eta, eta.at[idx], "ETA > ETC", ErrorType.OUT_OF_RANGE)
            _report_error(idx, col_etb, etb.at[idx], "ETA > ETC", ErrorType.OUT_OF_RANGE)
            _report_error(idx, col_etc, etc.at[idx], "ETA > ETC", ErrorType.OUT_OF_RANGE)
            eta_ord_raw.at[idx] = pd.NA
            etc_ord_raw.at[idx] = _OPEN_END
         else:
            _report_error(idx, col_etb, etb.at[idx], "ETB < ETA", ErrorType.OUT_OF_RANGE)
         continue

      if not c2:
         _report_error(idx, col_etb, etb.at[idx], "ETB > ETC", ErrorType.OUT_OF_RANGE)
         continue
   
   
   return (eta_ord_raw,etc_ord_raw)

def _cast_decimal(series : pd.Series, colname : str, vessel_series: pd.Series, report : ValidationReport)->pd.Series:
   original_na = series.isna()
   _dec = _to_decimal(series.to_numpy())
   _dec_series = pd.Series(_dec, index=series.index)

   new_errors = _dec_series.isna() & ~original_na
   error_values = series.iloc[new_errors]
   assert isinstance(error_values,pd.Series)

   if error_values.empty:
      return _dec_series
   
   for idx, value in error_values.items():
      assert isinstance(idx,int)
      reason = f"Valor '{value}' no es un decimal_valido"
      report.add_error(vessel_series.at[idx], idx, colname, value, reason, ErrorType.INVALID_VALUE)
      logger.error('Indice %s | %s | %s | %s', idx, colname, value, reason)
      
   return _dec_series


def _cast_enum(series : pd.Series, colname : str, enum_class : type[Enum], vessel_series: pd.Series, report : ValidationReport, is_nullable : bool = True)->pd.Series:
   def coerce_to_enum(val):
      if pd.isna(val):
         return None
      try:
         return enum_class(val).value
      except ValueError:
         return None

   original_na = series.isna()
   parsed = series.apply(coerce_to_enum)
   assert isinstance(parsed,pd.Series)
   if not is_nullable:
      null_values : pd.Series = series.loc[original_na]
      for idx, value in null_values.items():
         assert isinstance(idx,int)
         reason = "El valor no puede ser nulo o estar vacío"
         report.add_error(vessel_series.at[idx], idx, colname, value, reason, ErrorType.OUT_OF_RANGE)
         logger.error('Indice %s | %s | %s | %s', idx, colname, value, reason)

   new_errors = parsed.isna() & ~original_na
   error_values = series.loc[new_errors]
   
   if not error_values.empty:
      valid_values = [e.value for e in enum_class]
      for idx, value in error_values.items():
         reason = f"Valor '{value}' no es válido para {enum_class.__name__} (valores esperados: {valid_values})"
         report.add_error(vessel_series.at[idx], int(idx), colname, value, reason, ErrorType.MISSING_VALUE)
         logger.error('Indice %s | %s | %s | %s', idx, colname, value, reason)
      
   return parsed

class BaseLineUpProcessor(ABC, Generic[L,R]):
   """
   Clase abstracta que define un procesador para un lineup.
   """
   def __init__(self, layout_bundle : LayoutBundle[L,R]) -> None:
      self.bundle : LayoutBundle[L,R] = layout_bundle
      self.columns = Columns
      
   def process(self, wb : openpyxl.Workbook, port : str, port_match : str, config : dict, additional : LineUpValidationsData, current_date : datetime)->tuple[pd.DataFrame,ValidationReport]:
      ws = wb[port_match]
      valid_terminals = additional.get_terminals(port)
      valid_cargo = additional.get_vessel_cargo()
      company_blacklist = additional.get_black_list()
      
      header_row = config.get("header_row", 12)
      check_headers = config.get('matching',{}).get('check_headers',False)
      assert isinstance(check_headers,bool)
      df = self._read_sheet(ws, header_row,check_headers)        
      df,report = self._clean_common(df,self.bundle.load, valid_terminals, valid_cargo,company_blacklist, current_date)
      df,report = self._transform(df,report)  
      return df,report

   def _read_sheet(self, ws, header_row: int, check_headers : bool) -> pd.DataFrame:
      cols = self.bundle.load.get_sorted()
      min_col, max_col = cols[0].col, cols[-1].col

      rows_iter = ws.iter_rows(
          min_row=header_row,
          max_row=ws.max_row,
          min_col=min_col,
          max_col=max_col,
          values_only=True,
      )

      headers = next(rows_iter)
      df = pd.DataFrame(rows_iter, columns=headers, dtype=object)
      if check_headers:
         has_valid_headers(df.columns.tolist(), cols)

      col_names   = [c.name for c in cols]
      col_indices = [c.col - min_col for c in cols]
      df = df.iloc[:, col_indices].copy()
      df.columns = col_names
      return df

   def _clean_common(self, df: pd.DataFrame, layout : type[LineUpBaseLayout], terminals : list[str], vessel_cargo : pd.DataFrame, company_blacklist : set[str],current_date : datetime) -> tuple[pd.DataFrame,ValidationReport]:
      report = ValidationReport()
      idx = df[self.columns.VESSEL].isna().idxmax()
      if pd.isna(df.at[idx, self.columns.VESSEL]):
         df = df.iloc[:idx].reset_index(drop=True)
      vessel_series = df[self.columns.VESSEL]
      assert isinstance(vessel_series,pd.Series)
      for member in layout:
         col_name = member.name
         assert col_name in df.columns, f'la columna {col_name} no esta en {df.columns}'
         col_serie = df[col_name]
         assert isinstance(col_serie,pd.Series)
         match member.ideal_type:
            case "string":
               df[col_name] = _cast_string(col_serie)
            case "datetime":
               df[col_name] = _cast_datetime(col_serie, col_name, vessel_series, report)
            case "decimal":
               df[col_name] = _cast_decimal(col_serie, col_name, vessel_series, report)
            case "object":
               pass

      for col_name in [self.columns.DATE_OF_ARRIVAL_PERIOD, self.columns.ETB_PERIOD, self.columns.ETC_PERIOD]:
         col_serie = df[col_name]
         assert isinstance(col_serie,pd.Series)
         df[col_name] = _cast_enum(col_serie, col_name, enums.DatePeriod, vessel_series, report)

      ser_status =  df[self.columns.STATUS]
      ser_operation =  df[self.columns.OPERATION]
      ser_type = df[self.columns.TYPE]

      assert isinstance(ser_status,pd.Series)
      assert isinstance(ser_operation,pd.Series)
      assert isinstance(ser_type,pd.Series)

      df[self.columns.STATUS]    = _cast_enum(ser_status,    self.columns.STATUS,    enums.VesselStatus,    vessel_series, report, False)
      df[self.columns.OPERATION] = _cast_enum(ser_operation, self.columns.OPERATION, enums.OperationStatus, vessel_series, report, False)
      df[self.columns.TYPE]      = _cast_enum(ser_type,      self.columns.TYPE,      enums.CargoType,       vessel_series, report)

      df[self.columns.PIER]            = df[self.columns.PIER].str.replace(r'\s+', '', regex=True)

      ser_port_load = df[self.columns.PORT_LOAD_DISCH]
      assert isinstance(ser_port_load,pd.Series)
      
      df[self.columns.PORT_LOAD_DISCH] = _format_port_country(ser_port_load, self.columns.PORT_LOAD_DISCH, vessel_series, report)

      ser_terminal = df[self.columns.TERMINAL]
      assert isinstance(ser_terminal,pd.Series)
      
      if terminals:
         df[self.columns.TERMINAL] = _validate_terminals(
            ser_terminal, self.columns.TERMINAL, vessel_series, terminals, report
         )      
      
      df = _validate_cargo(
         df,
         self.columns.TYPE,
         self.columns.PRODUCT,
         self.columns.MT_BY_PRODUCT,
         self.columns.TOTAL_MT,
         self.columns.VESSEL,
         vessel_cargo,
         report,
      )
      
      # --- Preparación de Series para Intervalos de Tiempo ---
      ser_ata       = df[self.columns.DATE_OF_ARRIVAL]
      ser_ata_per   = df[self.columns.DATE_OF_ARRIVAL_PERIOD]
      ser_etb       = df[self.columns.ETB]
      ser_etb_per   = df[self.columns.ETB_PERIOD]
      ser_etc       = df[self.columns.ETC]
      ser_etc_per   = df[self.columns.ETC_PERIOD]

      # Aserciones para asegurar que Pyright reconozca las Series
      assert isinstance(ser_ata, pd.Series)
      assert isinstance(ser_ata_per, pd.Series)
      assert isinstance(ser_etb, pd.Series)
      assert isinstance(ser_etb_per, pd.Series)
      assert isinstance(ser_etc, pd.Series)
      assert isinstance(ser_etc_per, pd.Series)      
      
      ata_ordinal, etc_ordinal = _cast_et_interval(
         ser_ata,
         ser_ata_per,
         ser_etb,
         ser_etb_per,
         ser_etc,
         ser_etc_per,
         self.columns.DATE_OF_ARRIVAL,
         self.columns.DATE_OF_ARRIVAL_PERIOD,
         self.columns.ETB,
         self.columns.ETB_PERIOD,
         self.columns.ETC,
         self.columns.ETC_PERIOD,

         vessel_series,
         report,
      )
      df['_DATE_OF_ARRIVAL_ORD'] = ata_ordinal
      df['_ETC_ORD'] = etc_ordinal
      df = _validate_status(
         df,
         self.columns.STATUS,
         self.columns.OPERATION,
         self.columns.ETB,
         self.columns.ETC,
         self.columns.DATE_OF_ARRIVAL,
         self.columns.TYPE,
         self.columns.PRODUCT,
         self.columns.MT_BY_PRODUCT,
         self.columns.TOTAL_MT,
         self.columns.SHIPOWNER,
         self.columns.CHARTERER,
         self.columns.AGENCY,
         self.columns.VESSEL,
         company_blacklist,
         report,
         current_date
      )

      
      return df, report
   
   @abstractmethod
   def _transform(self, df : pd.DataFrame, report : ValidationReport)->tuple[pd.DataFrame,ValidationReport]:
      ...


class LineUpProcessor(BaseLineUpProcessor[LineUpLayout, LineUpReportLayout]):
   def _transform(self, df: pd.DataFrame, report : ValidationReport):
      return df, report


class VariantLineUpProcessor(BaseLineUpProcessor[LineUpVariantLayout,LineUpReportVariantLayout]):
   def _transform(self, df: pd.DataFrame, report : ValidationReport):
      col = self.bundle.load.WINDOWS.header
      df[col] = df[col].str.replace(" ", "", regex=False)
      
      original_na = df[col].isna()
      valid_mask = df[col].str.match(r"^\d{2}-\d{2}$")      
      invalid_mask = ~valid_mask & ~original_na
      invalid_values: pd.Series = df.loc[invalid_mask, col]
      
      if not invalid_values.empty:
         for idx, value in invalid_values.items():
            assert isinstance(idx,int)
            reason = f"Valor '{value}' no cumple formato esperado DD-DD (ej: 12-34)"
            report.add_error(df.at[idx, self.columns.VESSEL], int(idx), col, value, reason)
            logger.error(
                "Indice %s | %s | %s | %s",
                idx, col, value, reason
            )
      return df, report

def make_processor(layout_bundle : LayoutBundle):
   if layout_bundle is LineUpLayouts.variant:
      return VariantLineUpProcessor(layout_bundle)
   return LineUpProcessor(layout_bundle)

__all__ = [
   'make_processor',
   "LineUpProcessor",
   "VariantLineUpProcessor"
]

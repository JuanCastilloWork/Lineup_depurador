from ntpath import exists
import pandas as pd
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
   "VESSEL",
   "TERMINAL",
   "PORT_LOAD_DISCH",
   "CHARTERER",
   "AGENCY",
   "SHIPOWNER",
}
ROLES = ["CHARTERER", "AGENCY", "SHIPOWNER"]

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
   """Normaliza nombres de columnas: strip, mayúsculas, espacios → '_'."""
   import re
   def clean_name(name):
      # 1. Convertir a mayúsculas y limpiar bordes
      name = name.upper().strip()
      # 2. Reemplazar todo lo que NO sea letras (A-Z) o números (0-9) por '_'
      name = re.sub(r"[^A-Z0-9]+", "_", name)
      # 3. Limpiar guiones bajos sobrantes en los extremos (ej: _NOMBRE_ -> NOMBRE)
      return name.strip("_")

   df.columns = [clean_name(col) for col in df.columns]
   return df
def _validate_columns(df: pd.DataFrame, source: str) -> bool:
   """
   Verifica que todas las columnas requeridas existan en el DataFrame.
   Loggea cada columna faltante y retorna False si falta alguna.
   """
   missing = REQUIRED_COLUMNS - set(df.columns)
   if missing:
      for col in sorted(missing):
         logger.error("Columna requerida '%s' no encontrada en '%s'.", col, source)
      return False
   return True

def create_auxiliar_data(lineups_path : Path)->dict | None:
   logger.info("Iniciando proceso. Directorio: %s", lineups_path)
 
   if not lineups_path.exists():
      logger.error("El directorio '%s' no existe.", lineups_path)
      return None

   
   excel_files = [
      f for f in lineups_path.glob("*ACUMULADO*.xlsx")
      if not f.name.startswith("~$") and 'line up' in f.name.lower()
   ]

   if not excel_files:
      logger.warning("No se encontraron archivos line up ACUMULADO*.xlsx en '%s'.", lineups_path)
      return None

   logger.info("Archivos encontrados: %d", len(excel_files))
   
   company_records = []
   vessel_records = []
   port_terminal_records = []
   port_load_disch_records = []   

   output_path = lineups_path / 'output'
   output_path.mkdir(exist_ok=True)
   
   for lineup in excel_files:
      try:
         dfs = pd.read_excel(lineup, sheet_name=None, skiprows=3)
      except Exception as e:
         logger.error(e)
         return None
      for sheet_name, df in dfs.items():
         df = _normalize_columns(df)
       
         if not _validate_columns(df, f"{lineup.name} / hoja '{sheet_name}'"):
            logger.error(
               "Saltando hoja '%s' de '%s' por columnas faltantes.",
               sheet_name, lineup.name,
            )
            continue      
      
         vessel_records.append(df[["VESSEL"]].copy())
         
         for rol in ROLES:
            subset = df[[rol]].rename(columns={rol: "Company"})
            subset["Role"] = rol
            company_records.append(subset)
 
         pt = df[["TERMINAL"]].copy()
         pt["PORT"] = sheet_name.strip()
         port_terminal_records.append(pt)
 
         # PORT_LOAD_DISCH → separar por coma
         pld = df[["PORT_LOAD_DISCH"]].copy()
         pld_split = pld["PORT_LOAD_DISCH"].str.rsplit(",", n=1, expand=True)
         pld["PORT_LOAD_DISCH"] = pld_split[0].str.strip()
         pld["COUNTRY"] = pld_split[1].str.strip() if 1 in pld_split else None
         port_load_disch_records.append(pld)

   if not vessel_records:
       logger.error("No se procesó ninguna hoja válida.")
       return None
 
   df_port_terminal = (
       pd.concat(port_terminal_records, ignore_index=True)
       .dropna(subset=["TERMINAL"])
       .assign(
           PORT=lambda x: x["PORT"].str.strip(),
           TERMINAL=lambda x: x["TERMINAL"].str.strip(),
       )
       .drop_duplicates(subset=["PORT", "TERMINAL"])
       .sort_values(["PORT", "TERMINAL"])
       .reset_index(drop=True)
   )[["PORT", "TERMINAL"]]
 
   # --- PORT_LOAD_DISCH + COUNTRY ---
   df_ports_country = (
       pd.concat(port_load_disch_records, ignore_index=True)
       .dropna(subset=["PORT_LOAD_DISCH"])
       .assign(
           PORT_LOAD_DISCH=lambda x: x["PORT_LOAD_DISCH"].str.strip(),
           COUNTRY=lambda x: x["COUNTRY"].str.strip(),
       )
       .drop_duplicates(subset=["PORT_LOAD_DISCH", "COUNTRY"])
       .sort_values(["COUNTRY", "PORT_LOAD_DISCH"])
       .reset_index(drop=True)
   )[["PORT_LOAD_DISCH", "COUNTRY"]]
 
   # --- Compañías + roles ---
   df_counts = (
       pd.concat(company_records, ignore_index=True)
       .dropna(subset=["Company"])
       .assign(Company=lambda x: x["Company"].str.strip())
       .groupby(["Company", "Role"], as_index=False)
       .size()
       .rename(columns={"size": "Count"})
   )
   df_pivot = df_counts.pivot(index="Company", columns="Role", values="Count").reset_index()
   df_pivot.columns.name = None
   count_cols = {
       "CHARTERER": "charterer_count",
       "SHIPOWNER": "shipowner_count",
       "AGENCY": "agency_count",
   }
   df_pivot = df_pivot.rename(columns=count_cols).fillna(0)
   df_pivot["is_charterer"] = df_pivot["charterer_count"] > 0
   df_pivot["is_shipowner"] = df_pivot["shipowner_count"] > 0
   df_pivot["is_agency"] = df_pivot["agency_count"] > 0
   df_companies = df_pivot[[
       "Company",
       "is_charterer", "charterer_count",
       "is_shipowner", "shipowner_count",
       "is_agency",    "agency_count",
   ]].sort_values("Company").reset_index(drop=True)
 
   # --- Barcos únicos ---
   df_vessels = (
       pd.concat(vessel_records, ignore_index=True)
       .dropna(subset=["VESSEL"])
       .assign(VESSEL=lambda x: x["VESSEL"].str.strip())
       .drop_duplicates(subset=["VESSEL"])
       .sort_values("VESSEL")
       .reset_index(drop=True)
   )
 
   # --- Guardar resultados ---
   outputs = {
       "companies":    (df_companies,    "LINEUP_COMPANIES.xlsx"),
       "vessels":      (df_vessels,      "LINEUP_VESSELS.xlsx"),
       "ports_country":(df_ports_country,"LINEUP_PORT_COUNTRY.xlsx"),
   }
   outputs["port_terminal"] = (df_port_terminal, "LINEUP_PORT_TERMINAL.xlsx")
 
   for key, (df, filename) in outputs.items():
       out_path = output_path / filename
       df.to_excel(out_path, index=False)
       logger.info("Guardado: %s (%d filas)", out_path.name, len(df))
 
   logger.info("Proceso completado.")
   return {key: df for key, (df, _) in outputs.items()}

      
if __name__ == '__main__':
   import sys
   _here = Path(__file__).resolve()            # src/scripts/process_lineups.py
   sys.path.append(str(_here.parents[1]))      # agrega src/
 
   # Logger propio para ejecución directa — archivo simple, es migración puntual
   _log_path = _here.parents[2] / 'logs'       # project/logs/
   _log_path.mkdir(exist_ok=True)
   _file_handler = logging.FileHandler(
       _log_path / 'auxiliar_data.log',
       encoding='utf-8'
   )
   _file_handler.setFormatter(
       logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
   )
   logger.addHandler(_file_handler)
   logger.addHandler(logging.StreamHandler())  # también imprime en consola
   logger.setLevel(logging.INFO)

   lineups_path = Path(input('Ingresa la ruta donde estan los line ups acumulados : '))
   if not lineups_path.exists():
      exit()

   result = create_auxiliar_data(lineups_path)
   if result is None:
      logger.error("El proceso terminó con errores.")
      exit()

   logger.info("Listo. DataFrames generados: %s", list(result.keys()))

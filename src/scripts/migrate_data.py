"""
Script para crear migrar la informacion de los lineups usando las plantillas antiguas, y recreando con la nueva estructura

Este script solo sirve para mover la data, las validaciones que toca crear en excel, columnas auxiliares, etc, hay que crearlas
"""

from __future__ import annotations

from pathlib import Path
import re
import logging
import pandas as pd


logger = logging.getLogger('__main__')
 
# ── Constantes ────────────────────────────────────────────────────────────────
 
MONTH_MAP = {
   'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
   'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
   'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
   'ene': 1, 'abr': 4, 'ago': 8, 'dic': 12,
}
 
PERIOD_RE = re.compile(
   r'\b(a[\s.,/\\]*m[\s.,/\\]*|p[\s.,/\\]*m[\s.,/\\]*)\b',
   re.IGNORECASE
)
def parse_date_period(
   col: pd.Series,
   year: int = 2024
) -> tuple[pd.Series, pd.Series]:
   """
   Parsea una columna con valores como '26 - jan  a m', '28-jan am', '15-dec pm', etc.
   
   Parámetros
   ----------
   col  : pd.Series con strings de fecha
   year : año a asumir para construir la fecha (default 2024)
   
   Retorna
   -------
   dates   : pd.Series de tipo datetime64
   periods : pd.Series de strings ('AM', 'PM' o '')
   """
   
   def _parse_one(raw):
      if pd.isna(raw):
         return pd.NaT, pd.NA
      
      s = str(raw).strip()
      s = s.replace('.','')
      # --- 1. Extraer periodo (AM / PM) ---
      m = PERIOD_RE.search(s)
      if m:
         period = re.sub(r'\s+', '', m.group()).upper()   # 'a m' -> 'AM'
         s = s[:m.start()] + s[m.end():]                  # quitar del string
      else:
         period = ''
      
      # --- 2. Limpiar y separar día y mes ---
      # Eliminar caracteres que no sean alfanuméricos ni espacios
      s = re.sub(r'[^a-zA-Z0-9\s]', ' ', s).strip()
      tokens = s.split()
      
      day = month_num = None
      for tok in tokens:
         if tok.isdigit():
            day = int(tok)
         elif tok.lower() in MONTH_MAP:
            month_num = MONTH_MAP[tok.lower()]
      
      if day is None or month_num is None:
         return pd.NaT, pd.NA
      
      try:
         date = pd.Timestamp(year=year, month=month_num, day=day)
      except ValueError:
         date = pd.NaT
      
      return date, period

   results = col.apply(_parse_one)
   dates   = pd.Series([r[0] for r in results], index=col.index, name='fecha',  dtype='datetime64[ns]')
   periods = pd.Series([r[1] for r in results], index=col.index, name='periodo', dtype='object')
   
   return dates, periods   

def process_lineups(lineups_path: Path, office_ports: dict[str, list[str]], year : int):
   """
   Procesa los archivos de lineups para cada oficina/puerto.
 
   Parámetros
   ----------
   lineups_path : ruta a la carpeta con los .xlsx de lineups
   office_ports : dict mapping oficina -> lista de puertos
   """
   output_path = lineups_path / 'output'
   output_path.mkdir(exist_ok=True)
   logger.info("Iniciando procesamiento. Ruta: %s", lineups_path)
   
   for office, ports in office_ports.items():
      # Buscar el archivo .xlsx cuyo nombre (sin extensión) coincida con el nombre de la oficina
      matched_file = next(
         (
            f for f in lineups_path.glob('*.xlsx')
            if not f.name.startswith('~$')
            and office in f.stem.lower().replace(' ','_')
         ),
         None
      )      

      if matched_file is None:
         logger.warning("[%s] No se encontró archivo .xlsx, saltando.", office)
         continue

      logger.info("[%s] Cargando: %s | Puertos: %s", office, matched_file.name, ports)
      try:
         raw_sheets = pd.read_excel(matched_file, sheet_name=None, skiprows=11,dtype=object)
      except Exception as e:
         logger.error(e)
         continue
      # Normalizar keys: lowercase, trim, reemplazar espacios por _
      normalized_sheets = {
         re.sub(r'\s+', '_', k.strip().lower()): df
         for k, df in raw_sheets.items()
      }
      out_file = output_path / f'lineup_{office}.xlsx'      
      with pd.ExcelWriter(out_file,engine='openpyxl') as writer:
         

         for port in ports:
            df = normalized_sheets.get(port)
            if df is None:
               logger.warning(
                  "  [%s] Hoja no encontrada. Hojas disponibles: %s",
                  port, list(normalized_sheets.keys())
               )
               continue
            logger.info("  [%s] %d filas cargadas.", port, df.shape[0])
            for col in df.columns:
               df[col] = df[col].replace('TBC',pd.NA)

            for col in ['DATE OF ARRIVAL','ETB','ETC']:
               
               df[col],df[f'{col}_PERIOD'] = parse_date_period(df[col],year)
               cols = list(df.columns)
               period_col = f'{col}_PERIOD'
               cols.remove(period_col)
               insert_at = cols.index(col) + 1
               cols.insert(insert_at, period_col)
               df = df[cols]

            first_column = df.columns[0]
            na_ratio = df[first_column].isna().sum()/len(df)
            if na_ratio > 0.8:
               df = df.drop(columns=[first_column])
            else:            
               logger.warning(
                  "[%s] Primera columna '%s' tiene %.1f%% NAs — no dropeando.",
                  port, first_column, na_ratio * 100
               )
            out_file = output_path / f'lineup_{port}.xlsx'
            df.to_excel(writer, sheet_name = port, index=False, startrow=11, startcol=1)
            logger.info("  [%s] Guardado en: %s", port, out_file)
   logger.info("Procesamiento finalizado.")         

if __name__ == '__main__':
   import sys
   import json
   import logging
   from datetime import datetime
 
   _here = Path(__file__).resolve()            # src/scripts/process_lineups.py
   sys.path.append(str(_here.parents[1]))      # agrega src/
 
   # Logger propio para ejecución directa — archivo simple, es migración puntual
   _log_path = _here.parents[2] / 'logs'       # project/logs/
   _log_path.mkdir(exist_ok=True)
   _file_handler = logging.FileHandler(
       _log_path / 'data_migration.log',
       encoding='utf-8'
   )
   _file_handler.setFormatter(
       logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
   )
   logger.addHandler(_file_handler)
   logger.addHandler(logging.StreamHandler())  # también imprime en consola
   logger.setLevel(logging.INFO)
 
   # Cargar config desde la raíz del proyecto
   _config_path = _here.parents[2] / 'config.json'
   assert _config_path.exists(), f"No se encontró config.json en: {_config_path}"
 
   with open(_config_path, encoding='utf-8') as f:
       _config = json.load(f)
 
   assert 'office_ports' in _config, "La clave 'office_ports' no existe en config.json"
 
   _office_ports: dict[str, list[str]] = _config['office_ports']
 
   _lineups_path = Path(input('Ingresa la ruta de lineups: '))
   assert _lineups_path.exists(), f"La ruta no existe: {_lineups_path}"

   _current_year = datetime.now().year
   _year_input = input(f'Año de trabajo [{_current_year}]: ').strip()
 
   if _year_input:
      assert _year_input.isdigit(), f"El año debe ser un número entero, se recibió: '{_year_input}'"
      _year = int(_year_input)
      assert 1900 < _year < 9999, f"Año fuera de rango razonable: {_year}"
      if _year > _current_year + 1:
         _confirm = input(f'El año {_year} es más de un año en el futuro, ¿estás seguro? (s/n): ').strip().lower()
         assert _confirm == 's', "Año no confirmado, abortando."
   else:
      _year = _current_year 
   process_lineups(_lineups_path, _office_ports,_year)

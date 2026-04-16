
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))
import re
import pandas as pd

lineups_path = Path(input('Ingresa la ruta de lineups: '))
if not lineups_path.exists():
   exit()

OFFICE_PORTS: dict[str, list[str]] = {
    "buenaventura": ["buenaventura"],
    "santa_marta":  ["santa_marta", "puerto_brisa"],
    "tolú":         ["tolu", "coveñas"],
    "barranquilla": ["barranquilla"],
    "cartagena":    ["cartagena"],
}


MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
    'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    # aliases comunes
    'ene': 1, 'abr': 4, 'ago': 8,
    'dic': 12,
}

PERIOD_RE = re.compile(r'\b(a[\s.,/\\]*m[\s.,/\\]*|p[\s.,/\\]*m[\s.,/\\]*)\b', re.IGNORECASE)

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

for office, ports in OFFICE_PORTS.items():
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
      print(f"[{office}] No se encontró archivo, saltando...")
      continue

   print(f"[{office}] Cargando: {matched_file.name} | Puertos: {ports}")
   raw_sheets = pd.read_excel(matched_file, sheet_name=None, skiprows=11,dtype=object)
   # Normalizar keys: lowercase, trim, reemplazar espacios por _
   normalized_sheets = {
      re.sub(r'\s+', '_', k.strip().lower()): df
      for k, df in raw_sheets.items()
   }

   output_path = lineups_path /' output'
   output_path.mkdir(exist_ok=True)
   for port in ports:
      df = normalized_sheets.get(port)
      if df is None:
         print(f"  [{port}] Hoja no encontrada. Hojas disponibles: {list(normalized_sheets.keys())}")
         continue
      print(f"  [{port}] {df.shape[0]} filas cargadas")

      for col in df.columns:
         df[col] = df[col].replace('TBC',pd.NA)

      for col in ['DATE OF ARRIVAL','ETB','ETC']:
         
         df[col],df[f'{col}_PERIOD'] = parse_date_period(df[col],2026)
         cols = list(df.columns)
         period_col = f'{col}_PERIOD'
         cols.remove(period_col)
         insert_at = cols.index(col) + 1
         cols.insert(insert_at, period_col)
         df = df[cols]

      df.to_excel(output_path / f'lineup_{port}.xlsx', index=False)

      

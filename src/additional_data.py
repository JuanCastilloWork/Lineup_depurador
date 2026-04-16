"""
Archivo que contiene la implementacion de LineUpAditionalData, clase que se encarga de cargar y proveer con datos adicionales al lineup necesarios para la validacion 
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple
import openpyxl
import pandas as pd
import logging
logger = logging.getLogger(__name__)

class _TableDef(NamedTuple):
   """
   Define la estructura y ubicacion de una tabla de Excel

   Attr:
      sheet: Nombre de la hoja de Excel.
      table_name: Nombre de la tabla en Excel.
      columns: Lista de columnas que se desean usar dentro del programa (para omitir lo innecesario)
      index_col: Columna opcional para ser usada como indice del DataFrame
   """
   sheet: str
   table_name: str
   columns: list[str]
   index_col: str | None  = None

class CompanyRoles(NamedTuple):
   """
   Representacion booleana de los roles que puede tener una empresa  
   """
   # TODO: Es posible que necesite agregar lo de que si es problematica o no, para mostrarlo?  
   is_shipowner: bool
   is_charterer: bool
   is_agency: bool

# Definicion de las tablas que se van a encontrar
_TABLES: list[_TableDef] = [
   _TableDef(sheet="VESSELS",   table_name="VESSELS",             columns=["NAME"],                                                  index_col="NAME"),
   _TableDef(sheet="COMPANIES", table_name="COMPANIES",           columns=["NAME", "IS_CHARTERER", "IS_AGENCY", "IS_OWNER", "IS_PROBLEMATIC"], index_col="NAME"),
   _TableDef(sheet="PRODUCTS",  table_name="PRODUCTS",            columns=["PRODUCT_TYPE", "NAME"],                                  index_col="PRODUCT_TYPE"),
   _TableDef(sheet="PORTS",     table_name="COLOMBIAN_UBICATIONS", columns=["PORT", "TERMINAL"],                                     index_col="PORT"),
   _TableDef(sheet="PORTS",     table_name="GLOBAL_UBICATIONS",    columns=["PORT", "COUNTRY"],                                      ),
]

_ESCENCIAL_TABLES = [table for table in _TABLES if table.table_name in ['COLOMBIAN_UBICATIONS','PRODUCTS']]

# Valores invalidos para saltar
_INVALID_VALUES = {"-", "", "NONE", "N/A", "NA"}

def _clean(value) -> str | None:
   """
   Limpia valores individuales de una celda

   1. Convierte a string
   2. Elimina espacios, pasa mayusculas
   3. Los valores marcados como invalidos, los convierte como None
    
   """
   if value is None:
      return None
   s = str(value).strip().upper()
   return None if s in _INVALID_VALUES else s

def _read_named_table(
   workbook: openpyxl.Workbook,
   sheet_name: str,
   table_name: str,
   columns: list[str],
   index_col: str | None,
) -> pd.DataFrame:
   """
   Extrae una tabla nombrada de Excel, y la convierte en un DataFrame de pandas

   Args:
      workbook: Instancia cargada de openpyxl.
      sheet_name: Nombre de la hoja de trabajo.
      table_name: Nombre de la tabla de Excel (Excel Named Table).
      columns: Columnas específicas a mantener.
      index_col: Nombre de la columna para el índice.   

   Raises:
      ValueError: Si la tabla no existe o faltan columnas requeridas
   Returns:
      pd.DataFrame: Datos sin duplicados, y con sus valores Normalizados usando _clean
      
   """
   ws = workbook[sheet_name]

   if table_name not in ws.tables:
       raise ValueError(f"Tabla '{table_name}' no encontrada en hoja '{sheet_name}'")

   ref = ws.tables[table_name].ref          # e.g. "A1:D100"
   rows_iter = ws[ref]


   # Extraer headers y datos aplicando _clean
   headers = [_clean(cell.value) for cell in rows_iter[0]]#type: ignore
   data = [
       [_clean(cell.value) for cell in row]#type: ignore
       for row in rows_iter[1:]
   ]

   df = pd.DataFrame(data, columns=headers)

   # Verificar columnas requeridas
   missing = [c for c in columns if c not in df.columns]
   if missing:
      raise ValueError(
         f"Columnas {missing} no encontradas en tabla '{table_name}'. "
         f"Disponibles: {list(df.columns)}"
      )

   df = df[columns]                          # solo columnas requeridas
   df = df.dropna(how="all")                 # eliminar filas completamente vacías
   df = df.drop_duplicates()
   if index_col:
      df = df.set_index(index_col)
   assert isinstance(df,pd.DataFrame)
   return df


class LineUpValidationsData:
   """
   Clase que tiene todos los datos adicionales para las validaciones de Line Up

   Carga y provee acceso rapido para los buques historicos, roles de empresas, puertos y productos

   NOTA: El metodo de carga actualmente carga todo independiente de la necesidad, tenes que separar que carga y que no para que sea mas limpio
    
   """
   def __init__(self) -> None:
      self.colombian_ports: pd.DataFrame = pd.DataFrame()   # index=PORT,    col: TERMINAL
      self.historic_vessels: pd.DataFrame = pd.DataFrame()  # index=NAME
      self.companies: pd.DataFrame = pd.DataFrame()         # index=NAME,    cols: IS_CHARTERER, IS_AGENCY, IS_OWNER, IS_PROBLEMATIC
      self.country_ports: pd.DataFrame = pd.DataFrame()     # index=COUNTRY, col: PORT
      self.vessel_cargo: pd.DataFrame = pd.DataFrame()      # index=PRODUCT_TYPE, col: NAME

   def _load_escencial_data(self, wb : openpyxl.Workbook):
      for table_def in _ESCENCIAL_TABLES:
         try:
            df = _read_named_table(
               wb,
               sheet_name=table_def.sheet,
               table_name=table_def.table_name,
               columns=table_def.columns,
               index_col=table_def.index_col,
            )
            self._process(table_def.table_name, df)
         except Exception as e:
            logger.error('Error cargando la tabla %s: %s',table_def.table_name,e)


   def _load_additional_tables(self, wb : openpyxl.Workbook, tables : list[str]):
      
      for table in tables:
         for _table in _TABLES:
            if table == _table.table_name:
               try:
                  df = _read_named_table(wb, _table.sheet,_table.table_name,_table.columns,_table.index_col)         
                  self._process(_table.table_name,df)
               except Exception as e:
                  logger.error('Error cargando la tabla %s: %s',_table.table_name,e)

   
   def load(self, file_path: Path | str,load_vessels : bool = False, load_global_ports : bool = False, load_companies : bool = False ):
      file_path = Path(file_path)
      wb = openpyxl.load_workbook(file_path, read_only=False, data_only=True)
      self._load_escencial_data(wb)

      _aditional_tables = []
      if load_vessels:
         _aditional_tables.append('VESSELS')
      if load_global_ports:
         _aditional_tables.append('GLOBAL_UBICATIONS')
      if load_companies:
         _aditional_tables.append('COMPANIES')
      self._load_additional_tables(wb,_aditional_tables)
      wb.close()

   def _process(self, table_name: str, df: pd.DataFrame):
      mapping = {
         "VESSELS": "historic_vessels",
         "COMPANIES": "companies",
         "PRODUCTS": "vessel_cargo",
         "COLOMBIAN_UBICATIONS": "colombian_ports",
         "GLOBAL_UBICATIONS": "country_ports"
      }
      if table_name in mapping:
         setattr(self, mapping[table_name], df)

   def get_company_roles(self, names: list[str] | set[str]) -> dict[str, CompanyRoles]:
      """
      Metodo para obtener los roles de una lista de compañias (Este metodo se asume que buscas en compañias que ya existen dentro de los datos adicionales) 
      """
      result: dict[str, CompanyRoles] = {}
      for company, row in self.companies.loc[list(names)].iterrows():
          result[str(company)] = CompanyRoles(
            is_shipowner=True if row['IS_OWNER'] in ['TRUE',1,True] else False,
            is_charterer=True if row['IS_CHARTERER'] in ['TRUE',1,True] else False,
            is_agency=True if row['IS_AGENCY'] in ['TRUE',1,True] else False          )
      return result
   def get_all_companies(self):
      return self.companies.index

   def get_companies_by_role(
       self,
       *,
       charterers: bool = False,
       agencies: bool = False,
       owners: bool = False,
   ) -> dict[str, pd.Index]:
      """
      Retorna un dict con las empresas filtradas por rol.
      Claves presentes solo si el flag correspondiente es True:
        'charterers', 'agencies', 'owners'
      """
      result: dict[str, pd.Index] = {}
      if charterers:
         result["charterers"] = self.companies.index[
            self.companies["IS_CHARTERER"].notna()
         ]
      if agencies:
         result["agencies"] = self.companies.index[
      self.companies["IS_AGENCY"].notna()
         ]
      if owners:
         result["owners"] = self.companies.index[
            self.companies["IS_OWNER"].notna()
         ]
      return result
      

   def get_black_list(self) -> set[str]:
      """Retorna el conjunto de empresas marcadas como problemáticas."""
      if "IS_PROBLEMATIC" not in self.companies.columns:
         return set()
      mask = self.companies["IS_PROBLEMATIC"].notna()
      return set(self.companies.index[mask])

   def get_vessels(self) -> list[str]:
      return self.historic_vessels.index.tolist()
   def get_terminals(self, port: str) -> list[str]:
      if port not in self.colombian_ports.index:
         return []
      terminals = self.colombian_ports.loc[port, "TERMINAL"]
      # loc puede retornar un scalar o una Series si hay múltiples terminales
      return terminals.tolist() if isinstance(terminals, pd.Series) else [terminals]

   def get_vessel_cargo(self) -> pd.DataFrame:
      return self.vessel_cargo 

   def get_port_countries(self) -> list[str]:
      return (self.country_ports['PORT'] + ', ' + self.country_ports['COUNTRY']).tolist()

   

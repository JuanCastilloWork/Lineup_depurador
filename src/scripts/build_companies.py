import pandas as pd
from pathlib import Path
import sys



if __name__ == '__main__':

   CREATING_ALL = True
      
   sys.path.append(str(Path(__file__).resolve().parents[1]))
   from excel.layots import LineUpReportLayout
   lineup_path_user = Path(
      'C:/Users/Juan Castillo/proyectos/lineup_validacion/data/acumulados'
   )
   
   if not lineup_path_user.exists():
       exit()
   
   excel_files = [
       f for f in lineup_path_user.glob('*ACUMULADO*.xlsx')
       if not f.name.startswith('~$')
   ]
   
   start, end = LineUpReportLayout.col_range()
   a = list(range(1, end + 1, 1))
   colidx = [_.col for _ in LineUpReportLayout]
   b = [_ - 1 for _ in a if _ in colidx]
   
   roles = [
       LineUpReportLayout.CHARTERER.name,
       LineUpReportLayout.AGENCY.name,
       LineUpReportLayout.SHIPOWNER.name,
   ]
   
   company_records = []
   vessel_records = []
   port_terminal_records = []
   port_load_disch_records = []   

   for lineup in excel_files:
      dfs = pd.read_excel(lineup, sheet_name=None, skiprows=3, usecols=b)
   
      for sheet_name, df in dfs.items():
         df.columns = [c.name for c in LineUpReportLayout.get_sorted()]
   
         # --- Barcos únicos de este sheet ---
         vessel_records.append(df[['VESSEL']].copy())
   
         # --- Compañías con su rol ---
         for rol in roles:
            subset = df[[rol]].rename(columns={rol: 'Company'})
            subset['Role'] = rol
            company_records.append(subset)

         if CREATING_ALL:
            pt = df[['TERMINAL']].copy()
            pt['PORT'] = sheet_name.strip()
            port_terminal_records.append(pt)

         # PORT_LOAD_DISCH -> separar por coma
         pld = df[['PORT_LOAD_DISCH']].copy()
         pld_split = pld['PORT_LOAD_DISCH'].str.rsplit(',', n=1, expand=True)
         pld['PORT_LOAD_DISCH'] = pld_split[0].str.strip()
         pld['COUNTRY']         = pld_split[1].str.strip() if 1 in pld_split else None
         port_load_disch_records.append(pld)


   if CREATING_ALL:
      # DataFrame PORT + TERMINAL únicos
      df_port_terminal = (
          pd.concat(port_terminal_records, ignore_index=True)
          .dropna(subset=['TERMINAL'])
          .assign(
              PORT     = lambda x: x['PORT'].str.strip(),
              TERMINAL = lambda x: x['TERMINAL'].str.strip(),
          )
          .drop_duplicates(subset=['PORT', 'TERMINAL'])
          .sort_values(['PORT', 'TERMINAL'])
          .reset_index(drop=True)
      )[['PORT', 'TERMINAL']]
      df_port_terminal.to_excel(lineup_path_user / 'LINEUP_PORT_TERMINAL.xlsx',index = False)
   
   # DataFrame PORT_LOAD_DISCH + COUNTRY únicos
   df_ports_country = (
       pd.concat(port_load_disch_records, ignore_index=True)
       .dropna(subset=['PORT_LOAD_DISCH'])
       .assign(
           PORT_LOAD_DISCH = lambda x: x['PORT_LOAD_DISCH'].str.strip(),
           COUNTRY         = lambda x: x['COUNTRY'].str.strip(),
       )
       .drop_duplicates(subset=['PORT_LOAD_DISCH', 'COUNTRY'])
       .sort_values(['COUNTRY', 'PORT_LOAD_DISCH'])
       .reset_index(drop=True)
   )[['PORT_LOAD_DISCH', 'COUNTRY']]
     
   
   # DataFrame de compañías + roles

   
   df_counts = (
       pd.concat(company_records, ignore_index=True)
       .dropna(subset=['Company'])
       .assign(Company=lambda x: x['Company'].str.strip())
       .groupby(['Company', 'Role'], as_index=False)
       .size()
       .rename(columns={'size': 'Count'})
   )
   
   # Pivot: una fila por compañía
   df_pivot = df_counts.pivot(index='Company', columns='Role', values='Count').reset_index()
   df_pivot.columns.name = None
   
   # Columnas de conteo con nombre limpio
   count_cols = {
       LineUpReportLayout.CHARTERER.name:  'charterer_count',
       LineUpReportLayout.SHIPOWNER.name:  'shipowner_count',
       LineUpReportLayout.AGENCY.name:     'agency_count',
   }
   df_pivot = df_pivot.rename(columns=count_cols).fillna(0)
   
   # Flags booleanos
   df_pivot['is_charterer']  = df_pivot['charterer_count']  > 0
   df_pivot['is_shipowner']  = df_pivot['shipowner_count']   > 0
   df_pivot['is_agency']     = df_pivot['agency_count']      > 0
   # Orden final de columnas
   df_companies = df_pivot[[
       'Company',
       'is_charterer',  'charterer_count',
       'is_shipowner',  'shipowner_count',
       'is_agency',     'agency_count',
   ]].sort_values('Company').reset_index(drop=True)
   
   
   # Conteo de veces que cada compañía aparece en cada rol (histórico acumulado)   
   # DataFrame de barcos únicos históricos
   df_vessels = (
       pd.concat(vessel_records, ignore_index=True)
       .dropna(subset=['VESSEL'])
       .assign(VESSEL=lambda x: x['VESSEL'].str.strip())
       .drop_duplicates(subset=['VESSEL'])
       .sort_values('VESSEL')
       .reset_index(drop=True)
   )
   df_companies.to_excel(lineup_path_user / 'LINEUP_COMPANIES.xlsx',index=False)
   df_vessels.to_excel(lineup_path_user / 'LINEUP_VESSELS.xlsx',index = False)
   df_ports_country.to_excel(lineup_path_user / 'LINEUP_PORT_COUNTRY.xlsx',index = False)
      

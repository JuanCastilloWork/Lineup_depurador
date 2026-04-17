
from pathlib import Path
from datetime import datetime
from additional_data import LineUpValidationsData
from excel import ExcelResolver,LineUpLayouts
import tomllib
import logging
from logging.handlers import RotatingFileHandler
import openpyxl
from processors import make_processor,PostProcessor,PortBundle
from reports.client_report import LineUpExcelReport
from reports.validation import render_validation_report

Path('./logs/').mkdir(exist_ok=True)

file_handler = RotatingFileHandler('./logs/depuration.log',maxBytes=5*1024*1024, encoding='utf-8', backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)

TEST_USER_DATA_PATH = Path('./data/test_data/')
TEST_DATETIME = datetime(2026,3,20)

if __name__ == '__main__':
   logger.info('--- DEPURACION LINE UP ---')
   
   with open('config.toml','rb') as f:
      config = tomllib.load(f)

   logger.info('Se cargo la configuracion')
   logger.info('Cargando los datos adicionales')
   validation_data = LineUpValidationsData()
   vessel_matching_cfg = config.get('vessel_matching',{})
   company_matching_cfg = config.get('company_matching',{})
   company_matching_enabled = any({company_matching_cfg.get('check_charterer',False),company_matching_cfg.get('check_owner',False),company_matching_cfg.get('check_agency',False)})
   global_ubications_cfg = config.get('vessel_matching',{})

   
   validation_data.load(
      Path(config['additional_data_path']),
      vessel_matching_cfg.get('enabled',False),
      global_ubications_cfg.get('enabled',False),
      True,
   )
   logger.info('Datos adicionales cargados correctamente')
   min_score : int = config.get('matching',{}).get('min_score',80)
   assert isinstance(min_score,int) and min_score > 0 and min_score <= 100
   
   office_ports : dict[str,list[str]] = config.get('office_ports',{})
   assert isinstance(office_ports,dict) and office_ports
   assert all([isinstance(_,list) for _ in office_ports.values()])
   all_ports_len = sum(len(p) for p in office_ports.values())
   excel_layouts : dict[str,str] = config.get('layouts',{})
   
   # ------------------------------------------------------------------
   # Procesamiento por archivo / hoja  (primer processor)
   # ------------------------------------------------------------------   
   resolver = ExcelResolver(TEST_USER_DATA_PATH)
   valid_files = resolver.match_files(list(office_ports.keys()))

   bundles: dict[str, PortBundle] = {}
   for office, file_path in valid_files.items():
      logger.info("Procesando oficina '%s' — archivo: %s", office, file_path)
      wb = openpyxl.load_workbook(file_path, data_only=True)      
      valid_sheets = resolver.match_sheets(wb,office_ports[office],min_score)
      
      for port,port_match in valid_sheets.items():
         
         layout_key = str(excel_layouts.get(port.lower().strip(), 'default')).lower().strip()
         layout_bundle = LineUpLayouts.variant if layout_key == 'variant' else LineUpLayouts.base
         
         logger.info("  Puerto '%s' — layout: %s", port, layout_key)
         processor = make_processor(layout_bundle)
         df, report = processor.process(wb,port, port_match, config,validation_data,TEST_DATETIME)
         df['PORT'] = port.upper()
         df['_IDX'] = df.index
         bundles[port] = PortBundle(
            port=port.upper(),
            df=df,
            report=report,
            layout=layout_bundle.report,
         )
         logger.info("  Puerto '%s' procesado — %d filas", port, len(df))            

      wb.close()

  
   logger.info(
      "Primer procesamiento completo — %d puerto(s) cargados.", len(bundles)
   )
   # ------------------------------------------------------------------
   # Post-procesamiento global (segundo processor)
   # ------------------------------------------------------------------

   logger.info('Iniciando post-procesamiento global')
   post = PostProcessor(
       bundles=bundles,
       config=config,
       validation_data=validation_data,
   )
   post.run()
   logger.info('Post-procesamiento completo')
   port_report = {port: b.report for port, b in bundles.items()}
   
   template_path = Path(config['template_path'])
   output_path   = Path(config['output_path'])
   assets_dir    = Path(config['assets_dir'])
 
   render_validation_report(
       port_report,
       {'total_rows': sum(len(b.df) for b in bundles.values()), 'total_ports': all_ports_len},
       post.match_report,
       post.get_vessel_overlaps,
       template_path,
       output_path,
       assets_dir,
       config,
   )

   bundles = post.get_port_bundles()
   client_report = LineUpExcelReport(
      bundles,           # dict[str, PortBundle] — reemplaza los 3 dicts separados
      config['company']['name'],
      TEST_DATETIME,
   )
   client_report.create_report(header_row=config['header_row'])

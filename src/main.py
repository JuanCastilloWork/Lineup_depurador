from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
import logging
from typing import Any
import flet as ft
import json
import re
from typing import Callable

HEX_PATTERN = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')

Path('./logs/').mkdir(exist_ok=True)

file_handler = RotatingFileHandler('./logs/depuration.log',maxBytes=5*1024*1024, encoding='utf-8', backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)   
logger.info('--- Inicio App ---')

DARK_THEME = ft.Theme(
   color_scheme=ft.ColorScheme(
      primary=ft.Colors.INDIGO_300,
      on_surface=ft.Colors.with_opacity(0.85, ft.Colors.WHITE),        # texto normal
      on_surface_variant=ft.Colors.with_opacity(0.2, ft.Colors.WHITE), # texto disabled
   ),
   
)
LIGHT_THEME = ft.Theme(
   color_scheme_seed= ft.Colors.PURPLE_100
   
)
CONFIG_PATH = Path('./config.json')
CONFIG_PATH_ALTERNATIVE = Path('./config.example.json')

def _load_config() -> dict:
   logger.info('Cargando configuraciòn')
   with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
      config = json.load(f)
      logger.info('Configuracion cargada')
   return config
   
def _save_config(config: dict):
   logger.info('Guardando configuraciòn')
   with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
      json.dump(config, f, indent=2, ensure_ascii=False)
   logger.info('Configuracion guardada')

@dataclass
@ft.observable
class LineUpModel:
   in_charge_name: str = ""
   in_charge_area: str = ""
   highlight_style_color: str = ""
   highlight_style_company_name: str = ""
   highlight_style_bold : bool = True
   client_report_prefix: str = ""
   client_report_overwrite : bool = False
   is_editing : bool = False
   processing_header_row: int = 12
   processing_check_headers: bool = False
   processing_add_summary: bool = True
   matching_company_strategy : str = 'global'
   matching_company_simple : int = 80
   matching_company_partial : int = 80
   matching_company_token : int = 80
   matching_company_charterer_enabled : bool = False
   matching_company_owner_enabled : bool = False
   matching_company_agency_enabled : bool = False
   
   def change_editing_mode(self):
      self.is_editing = not self.is_editing

   def change_overwrite_file_report(self):
      self.client_report_overwrite = not self.client_report_overwrite

   def set_config(self, attr : str, value : Any):
      assert hasattr(self,attr), f'LineUpModel no tiene el atributo {attr}'
      print(f'Cambiando el atributo {attr} a {value}')
      setattr(self,attr,value)

   def to_config(self, base_config : dict)->dict:
      base_config['metadata']['in_charge']['name'] = self.in_charge_name
      base_config['metadata']['in_charge']['area'] = self.in_charge_area
      base_config['client_report']['highlight_style']['name'] = self.highlight_style_company_name
      base_config['client_report']['highlight_style']['color'] = self.highlight_style_color
      base_config['client_report']['highlight_style']['bold'] = self.highlight_style_bold
      base_config['client_report']['filename_prefix'] = self.client_report_prefix
      base_config['processing']['header_row'] = self.processing_header_row
      base_config['processing']['check_headers'] = self.processing_check_headers
      base_config['processing']['add_summary'] = self.processing_add_summary
      return base_config

def use_dialog(dialog_factory: Callable[[], ft.AlertDialog]) -> Callable[[], None]:
   from typing import cast, Optional
   dlg_ref = ft.use_ref(cast(Optional[ft.AlertDialog], None))
   if dlg_ref.current is None:
      dlg_ref.current = dialog_factory()
   def open_dialog():
      if dlg_ref.current:
         ft.context.page.show_dialog(dlg_ref.current)
   return open_dialog

@ft.component
def DepurationDialogContent(dep_config : DepurationConfig):
   def handle_date_change(e : ft.Event[ft.TextField]):
      lineup_date = e.control.value
      dep_config.update_date(lineup_date)   
         
   datefield = ft.TextField(dep_config.date, label='Line up date', on_change= handle_date_change)
   return ft.Column(
      height=125,
      controls=[
         ft.TextField(
             dep_config.lineup_paths,
             hint_text='Theres no folder selected',
             label='Folder',
             read_only=True,
         ),
         datefield,
      ]
   )

@dataclass
@ft.observable
class DepurationConfig:
   date : str = datetime.now().strftime('%d/%m/%Y')
   lineup_paths : str = ''

   def update_date(self, new_date : str):
      self.date = new_date
   
@ft.component
def LineUpConfigComponent():      
   
   def start_new_depuration(e):
      
      ft.context.page.pop_dialog()
      
      try:
         lineup_date = datetime.strptime(dep_config.date,'%d/%m/%Y')
      except Exception as ex:
         ft.context.page.show_dialog(ft.SnackBar('Invalid date, aborting depuration',bgcolor=ft.Colors.RED))   
         return

      def run():
         try:
            depurate_lineups(lineup_date)
         except Exception as ex:
            ft.context.page.show_dialog(ft.SnackBar(f'Theres ended with an error {ex}', bgcolor=ft.Colors.RED_200))
            logger.error(ex)
            return 
         
         ft.context.page.show_dialog(ft.SnackBar(f'The execution ended ', bgcolor=ft.Colors.GREEN_200))
      
      ft.context.page.show_dialog(ft.SnackBar('Start depuration'))
      ft.context.page.run_thread(run)

   def depurate_lineups(lineup_date : datetime):
      
      _config = app.to_config(config)
      from additional_data import LineUpValidationsData
      from excel import ExcelResolver,LineUpLayouts
      import openpyxl
      from processors import make_processor,PostProcessor,PortBundle
      from reports.client_report import LineUpExcelReport
      from reports.validation import render_validation_report
      
      validation_data = LineUpValidationsData()
      matching_config = _config['matching']
      vessel_matching_cfg = matching_config.get('vessel',{})
      company_matching_cfg = _config.get('company',{})
      company_matching_enabled = any({company_matching_cfg.get('check_charterer',False),company_matching_cfg.get('check_owner',False),company_matching_cfg.get('check_agency',False)})
      global_ubications_cfg = matching_config.get('port',{})

      validation_data.load(
         Path(_config['external_files']['additional_data_path']),
         vessel_matching_cfg.get('enabled',False),
         global_ubications_cfg.get('enabled',False),
         True,
      )

      logger.info('Datos adicionales cargados correctamente')
      min_score : int = matching_config.get('min_score',80)
      assert isinstance(min_score,int) and min_score > 0 and min_score <= 100
      
      office_ports : dict[str,list[str]] = _config.get('office_ports',{})
      assert isinstance(office_ports,dict) and office_ports
      assert all([isinstance(_,list) for _ in office_ports.values()])
      all_ports_len = sum(len(p) for p in office_ports.values())
      excel_layouts : dict[str,str] = _config.get('layouts',{})
      
      # ------------------------------------------------------------------
      # Procesamiento por archivo / hoja  (primer processor)
      # ------------------------------------------------------------------   

      execution_path = Path(dep_config.lineup_paths)
      resolver = ExcelResolver(execution_path)
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
            df, report = processor.process(wb,port, port_match, _config,validation_data,lineup_date)
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
          config=_config,
          validation_data=validation_data,
      )
      post.run()
      logger.info('Post-procesamiento completo')
      port_report = {port: b.report for port, b in bundles.items()}

      client_report_config = _config['client_report']
      client_report_template = client_report_config['template']
      
      template_path = Path(client_report_template['file'])
      output_path   = Path(execution_path) / 'output'
      output_path.mkdir(exist_ok=True)
      output_depuration = output_path / f'Line up depuration {lineup_date.strftime('%d-%m-%Y')}.html'
      
      assets_dir = Path(client_report_template['assets'])
 
      render_validation_report(
          port_report,
          {'total_rows': sum(len(b.df) for b in bundles.values()), 'total_ports': all_ports_len},
          post.match_report,
          post.get_vessel_overlaps,
          template_path,
          output_depuration,
          assets_dir,
          _config,
      )

      bundles = post.get_port_bundles()
      client_report = LineUpExcelReport(
         bundles,           # dict[str, PortBundle] — reemplaza los 3 dicts separados
         client_report_config['highlight_style']['name'],
         lineup_date
      )
      client_report.create_report(output_path /f'Line up {lineup_date.strftime('%d-%m-%Y')}.xlsx',header_row=_config['processing']['header_row'])

   async def on_create_axiliar_files(e):
      lineups_path = await ft.FilePicker().get_directory_path()
      from scripts.create_auxiliar_files import create_auxiliar_data
      if lineups_path is None:
         return
      def run():
         create_auxiliar_data(Path(lineups_path))

         ft.context.page.show_dialog(ft.SnackBar(f'Creation complete, result in {lineups_path}', bgcolor=ft.Colors.GREEN_400))
      
      ft.context.page.show_dialog(ft.SnackBar('Creating auxiliar files'))
      ft.context.page.run_thread(run)
      
   async def on_migrate_data(e):
      lineups_path = await ft.FilePicker().get_directory_path()
      from scripts.migrate_data import process_lineups
      if lineups_path is None:
         return
      def run():
         process_lineups(Path(lineups_path), config['office_ports'], 2026)
         ft.context.page.show_dialog(ft.SnackBar(f'Migration complete, result in {lineups_path}', bgcolor=ft.Colors.GREEN_400))

      ft.context.page.show_dialog(ft.SnackBar('Migration starts'))
      ft.context.page.run_thread(run)
   def on_change_editing_mode(e):
      app.change_editing_mode()

   def on_change_overwrite_client_report(e):
      app.change_overwrite_file_report()

   def save_config(e):
      _save_config(app.to_config(_load_config()))

   def section_title(title : str):
      return ft.Text(title, size = 13, weight=ft.FontWeight.W_600,color=ft.Colors.ON_SECONDARY_CONTAINER)

   def section_divider():
      return ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT)

   def handle_start_new_depuration(e):
      open_depuration_dialog()

   async def handle_folder_pick(e):
      folder_path = await ft.FilePicker().get_directory_path()
      if folder_path is None:
         return
      dep_config.lineup_paths = folder_path
   
   config,_ = ft.use_state(_load_config())
   app, _ = ft.use_state(LineUpModel(
        in_charge_name=config['metadata']['in_charge']['name'],
        in_charge_area=config['metadata']['in_charge']['area'],
        highlight_style_company_name=config['client_report']['highlight_style']['name'],
        highlight_style_color=config['client_report']['highlight_style']['color'],
        highlight_style_bold=config['client_report']['highlight_style']['bold'],
        client_report_prefix=config['client_report']['filename_prefix'],
        client_report_overwrite=config['client_report']['overwrite'],
      )
   )
   
   dep_config= ft.use_memo(lambda : DepurationConfig())

   open_depuration_dialog = use_dialog(
      lambda: ft.AlertDialog(
         title=ft.Text('Confirm information'),
         actions=[
            ft.FilledButton('Depurate', on_click= start_new_depuration),
            ft.FilledButton('Change folder', on_click=handle_folder_pick),
         ],
         content=DepurationDialogContent(dep_config),
      )
   )
   return ft.Container(
      border_radius=8,
      padding=18,
      content = ft.Column(
         spacing=20,
         controls = [
            ft.Row(
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
               controls = [
                  ft.Text(
                     'Daily Line Up Config', size= 28, weight=ft.FontWeight.BOLD,
                  ),
                  ft.Container(
                     content = ft.Row(
                        controls = [
                           ft.Switch(
                              value = app.is_editing,
                              on_change= on_change_editing_mode,
                              label= 'Edit'
                           ),
                           ft.FilledButton(
                              content=ft.Text('Save'),
                              icon=ft.Icons.SAVE,
                              disabled=not app.is_editing,
                              on_click=save_config
                           )
                        ]
                     )
                  )
                  
               ]
            
            ),

            ft.Row(
               alignment=ft.MainAxisAlignment.START,
               controls = [
                  ft.FilledButton('Depurate', on_click = handle_start_new_depuration),
               ]
            ),
            
            section_divider(),
            section_title('In charge'),
            ft.Row(
               spacing=12,
               controls = [            
                  ft.TextField(
                     value= app.in_charge_name,
                     label='Employee', expand=True,disabled=not app.is_editing,
                     on_change=lambda e: app.set_config('in_charge_name',e.control.value),
                  ),
                  ft.TextField(
                     value= app.in_charge_area,
                     label='Area', expand=True,disabled=not app.is_editing,
                     on_change=lambda e: app.set_config('in_charge_area',e.control.value)
                  ),
               ]
            ),

            section_divider(),
            ft.Row(
               alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
               controls = [            
                  section_title('Client report'),
                  ft.Switch(
                     value=app.client_report_overwrite,
                     disabled=not app.is_editing,
                     label='Overwrite file',
                     on_change=on_change_overwrite_client_report
                  )
               ]
            ),
            ft.TextField(
               value = app.highlight_style_company_name,
               label='Company to highlight', disabled=not app.is_editing,expand=True,
               on_change=lambda e: app.set_config('highlight_style_company_name',e.control.value)
            ),
            ft.TextField(
               value= app.client_report_prefix,
               label='File output prefix', expand=True,disabled=not app.is_editing,
               on_change=lambda e: app.set_config('filename_prefix',e.control.value)
            ),
            ft.Row(
               spacing=12,
               controls=[
                  ft.TextField(
                     value=app.highlight_style_color,
                     label='Color de compañía (hex)',
                     disabled=not app.is_editing,
                     expand=True,
                     on_change=lambda e: app.set_config('highlight_style_color', e.control.value) if bool(HEX_PATTERN.match(e.control.value)) else None,
                     input_filter=ft.InputFilter(allow = True, regex_string = r'[#0-9a-fA-F]'),
                  ),
                  ft.Container(
                     width=42,
                     height=42,
                     border_radius=8,
                     bgcolor=app.highlight_style_color,
                     border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                     tooltip=app.highlight_style_color
                  )
               ]
            ),

            section_divider(),
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    section_title('Processing'),
                    ft.Row(
                        spacing=4,
                        controls=[
                            ft.Switch(
                                value=app.processing_check_headers,
                                disabled=not app.is_editing,
                                label='Check headers',
                                on_change=lambda e: app.set_config('processing_check_headers', e.control.value)
                            ),
                            ft.Switch(
                                value=app.processing_add_summary,
                                disabled=not app.is_editing,
                                label='Add summary',
                                on_change=lambda e: app.set_config('processing_add_summary', e.control.value)
                            ),
                        ]
                    )
                ]
            ),
            ft.TextField(
                value=str(app.processing_header_row),
                label='Header row',
                helper='Excel 1-index',
                disabled=not app.is_editing,
                input_filter=ft.InputFilter(allow=True, regex_string=r'^[0-9]*$'),
                max_length=2,
                on_change=lambda e: app.set_config('processing_header_row', int(e.control.value))
                    if re.match(r'^([2-9]|1[0-5]?)$', e.control.value) else None,
                error=None if re.match(r'^([2-9]|1[0-5]?)$', str(app.processing_header_row)) else 'Valor inválido (1-15)',
            ),

            section_divider(),
            section_title('Auxiliar scripts'),
            ft.Row(
               alignment=ft.MainAxisAlignment.START,
               controls = [
                  ft.FilledButton(
                     "Create auxiliar files",
                     on_click=on_create_axiliar_files
                  ),
                  ft.FilledButton(
                     "Migrate templates",
                     on_click=on_migrate_data
                  ),
               ]
            ),
            ft.Container(
               bgcolor=ft.Colors.PRIMARY_CONTAINER,
               border_radius=8,
               padding=15,
               content = ft.Image(
                  src='company_logo.png',
                  height=145,
                  align=ft.Alignment.CENTER
               ),
            ),
 
         ]
      )
   )
@ft.component
def LineUpView():
   config_exists, set_config_exists = ft.use_state(CONFIG_PATH.exists())

   def create_config_from_example(e):
      from shutil import copy
      example_path = CONFIG_PATH.parent / "config.example.json"
      if example_path.exists():
         copy(example_path, CONFIG_PATH)
         set_config_exists(True)

   if not config_exists:
      return ft.View(
         route='/',
         horizontal_alignment=ft.CrossAxisAlignment.CENTER,
         vertical_alignment=ft.MainAxisAlignment.CENTER,
         controls=[
            ft.Column(
               horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=16,
               controls=[
                  ft.Icon(
                     ft.Icons.SETTINGS_SUGGEST_OUTLINED,
                     size=64,
                     color=ft.Colors.OUTLINE,
                  ),
                  ft.Text(
                     "No config found",
                     size=22,
                     weight=ft.FontWeight.BOLD,
                  ),
                  ft.Text(
                     "Theres no configuration file, do you wanna create using the example?",
                     size=14,
                     color=ft.Colors.ON_SURFACE_VARIANT,
                     text_align=ft.TextAlign.CENTER,
                     width=340,
                  ),
                  ft.FilledButton(
                     "Create config.json using the example",
                     icon=ft.Icons.FILE_COPY_OUTLINED,
                     on_click=create_config_from_example,
                  ),
               ],
            )
         ],
      )   
   
   return ft.View(
      route='/',
      horizontal_alignment=ft.CrossAxisAlignment.CENTER,
      scroll=ft.ScrollMode.ALWAYS,
      controls = [
         LineUpConfigComponent(),
      ]
   )

def main(page : ft.Page):
   page.title = 'Daily line up depurator'
   page.theme = LIGHT_THEME
   page.dark_theme = DARK_THEME
   page.window.width = 650
   page.window.height = 750
   page.window.resizable = False
   page.window.maximizable = False
   page.render_views(LineUpView)

if __name__ == '__main__':
   ft.run(main, assets_dir='assets')

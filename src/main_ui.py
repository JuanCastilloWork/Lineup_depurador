from dataclasses import dataclass, field
from pathlib import Path
from logging.handlers import RotatingFileHandler
import logging
from typing import Any
import flet as ft
import json

from openpyxl.styles import Color

from reports import client_report

Path('./logs/').mkdir(exist_ok=True)

file_handler = RotatingFileHandler('./logs/depuration.log',maxBytes=5*1024*1024, encoding='utf-8', backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)   
logger.info('--- Inicio App ---')

DARK_THEME = ft.Theme(
   color_scheme_seed= ft.Colors.BLUE_800
)
LIGHT_THEME = ft.Theme(
   color_scheme_seed= ft.Colors.BLUE_600
   
)
CONFIG_PATH = Path('./config.json')

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
      return base_config
      

@ft.component
def LineUpConfigComponent():
   config, set_config = ft.use_state(_load_config())
   app, _ = ft.use_state(LineUpModel(
        in_charge_name=config['metadata']['in_charge']['name'],
        in_charge_area=config['metadata']['in_charge']['area'],
        highlight_style_company_name=config['client_report']['highlight_style']['name'],
        highlight_style_color=config['client_report']['highlight_style']['color'],
        highlight_style_bold=config['client_report']['highlight_style']['bold'],
        client_report_prefix=config['client_report']['filename_prefix'],
        client_report_overwrite=config['client_report']['overwrite'],
    ))   

   ft.use_effect(_load_config)
   
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
   
   return ft.Container(
      bgcolor=ft.Colors.PRIMARY_CONTAINER,
      border_radius=8,
      padding=18,
      content = ft.Column(
         spacing=20,
         controls = [
            ft.Row(
               alignment=ft.MainAxisAlignment.END,
               controls = [
                  ft.Switch(
                     value = app.is_editing,
                     on_change= on_change_editing_mode,
                     label= 'Editar'
                  ),
                  ft.FilledButton(
                     content=ft.Text('Guardar'),
                     icon=ft.Icons.SAVE,
                     disabled=not app.is_editing,
                     on_click=save_config
                  )

                  
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
                     on_change=lambda e: app.set_config('in_charge_name',e.control.value)
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
                     
                  )
               ]
            ),
            ft.TextField(
               value = app.highlight_style_company_name,
               label='Company to highlight', disabled=not app.is_editing,
               on_change=lambda e: app.set_config('highlight_style_company_name',e.control.value)
            ),
            ft.Row(
               spacing=12,
               controls = [
                  ft.TextField(
                     value= app.client_report_prefix,
                     label='File output prefix', expand=True,disabled=not app.is_editing,
                     on_change=lambda e: app.set_config('filename_prefix',e.control.value)
                  ),
               ] 
            ),
         ]
      )
   )

def LineUpView():
   
   return ft.View(
      route='/',
      horizontal_alignment=ft.CrossAxisAlignment.CENTER,
      scroll=ft.ScrollMode.ALWAYS,
      controls = [
         ft.Container(
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            border_radius=8,
            content = ft.Image(
               src='company_logo.png',
               height=145,
               align=ft.Alignment.CENTER
            ),
         ),
         ft.Text(
            'Daily Line Up Config', size= 28, weight=ft.FontWeight.BOLD,
         ),
         LineUpConfigComponent()
      ]
   )

def main(page : ft.Page):
   page.theme = LIGHT_THEME
   page.dark_theme = DARK_THEME
   page.window.width = 650
   page.window.height = 750
   page.window.resizable = False
   page.window.maximizable = False
   page.render_views(LineUpView)

if __name__ == '__main__':
   ft.run(main, assets_dir='assets')

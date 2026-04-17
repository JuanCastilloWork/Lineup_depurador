from dataclasses import dataclass
from pathlib import Path
from logging.handlers import RotatingFileHandler
import logging
import flet as ft
import tomllib

Path('./logs/').mkdir(exist_ok=True)

file_handler = RotatingFileHandler('./logs/depuration.log',maxBytes=5*1024*1024, encoding='utf-8', backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

DARK_THEME = ft.Theme(
   color_scheme_seed= ft.Colors.BLUE_800
)
LIGHT_THEME = ft.Theme(
   color_scheme_seed= ft.Colors.BLUE_600
   
)

@ft.component
def LineUpView():
   config, set_config = ft.use_state({})
   
   def load_lineup_config():
      with open('config.toml','rb') as f:
         config = tomllib.load(f)
      set_config(config)
      print(config)

   ft.use_effect(load_lineup_config,[]) # Para que lance siempre
   
   return ft.View(
      route='/',
      horizontal_alignment=ft.CrossAxisAlignment.CENTER,
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
            'Line Up Diario Config', size= 28, weight=ft.FontWeight.BOLD,
         ),
         ft.Container(
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            border_radius=8,
            content = ft.Column(
               controls = [
                  ft.TextField(
                     
                  )
               ]
            )
         )
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

# report.py
from __future__ import annotations
from datetime import datetime,date
from pathlib import Path
from typing import Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
import logging
from validations import ValidationReport
from validations import error_registry
from validations.error_registry import CellError


logger = logging.getLogger(__name__)


meses = [
   "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
   "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

def _build_context(port_report : dict[str, ValidationReport], report_metadata : dict,match_report : dict,vessel_overlap, conf : dict)->dict:

   maintainer = conf.get('maintainer','Deep blue')
   area = conf.get('area','comercial')
   header_row : int | None = conf.get('header_row')
   if header_row:
      assert isinstance(header_row,int)
   else:
      logger.warning('No se proporciono el donde empieza el header en la configuracion,se asume que el header esta ubicado en la posicion 1 de excel')
      header_row = 1
   total_errors = 0
   total_warnings = 0
   total_row_errors = 0
   total_row_warnings = 0
   errors_by_type : dict[str,int] = {}
   warnings_by_type : dict[str,int] = {}
   port_cell_errors : dict[str, dict[int,list[CellError]]] = {}
   errors_by_port : dict[str,int] = {}
   vessel_report_by_port : dict[str,dict[str,dict[int,dict[str,list]]] ] = {}
   for port,report in port_report.items():
      total_errors += report.total_errors()
      total_warnings += report.total_warnings()
      rows_with_issues = report.rows_with_issues_count()
      vessels_errors = report.issues_by_vessel_and_row()
      vessel_report_by_port[port] = vessels_errors
      total_row_errors += rows_with_issues[0]
      total_row_warnings += rows_with_issues[1]
      errors_by_port[port] = report.total_errors()
      for error_type, count in report._errors_type.items():
         if error_type.value not in errors_by_type:
            errors_by_type[error_type.value] = 0 
         errors_by_type[error_type.value]+= count

      for warning_type, count in report._warnings_type.items():
         if warning_type.value not in warnings_by_type:
            warnings_by_type[warning_type.value] = 0 
         warnings_by_type[warning_type.value]+= count
      
   warnings_by_type_sort = sorted(warnings_by_type.items(), key=lambda x: x[1])  # menor a mayor por count
   errors_by_type_sort   = sorted(errors_by_type.items(),   key=lambda x: x[1], reverse=True)  # mayor a menor
   current_day = datetime.now()   
   return {
      'generated_at':f'{current_day.day} de {meses[current_day.month-1]} {current_day.year}',
      'ports' : list(port_report.keys()),
      'maintainer':maintainer,
      'area':area,
      'errors': total_errors,
      'warnings':total_warnings,
      'show_warnings':True,
      'header_row':header_row,
      'total_rows':report_metadata['total_rows'],
      'total_ports':report_metadata['total_ports'],
      'total_row_errors' : total_row_errors,
      'total_row_warnings' : total_row_warnings,
      'port_cell_errors' : port_cell_errors,
      'errors_by_type':errors_by_type_sort,
      'warnings_by_type':warnings_by_type_sort,
      'errors_by_port': errors_by_port,
      'vessel_report_by_port':vessel_report_by_port,
      'match_report':match_report,
      'vessel_overlap':vessel_overlap,
   }

def copy_assets(assets_dir : Path, output_path : Path)->bool:
   import shutil
   if not assets_dir.exists():
      logger.error(f"No existe el directorio origen: {assets_dir}")
      return False

   final_output_path = output_path / assets_dir.name
   
   if final_output_path.exists() and not final_output_path.is_dir():
      logger.error(f"El destino existe pero no es un directorio: {final_output_path}")
      return False   
   try:
      shutil.copytree(str(assets_dir),str(final_output_path), dirs_exist_ok=True, ignore= shutil.ignore_patterns('~$*','*.tmp','~*') )
      logger.info(f"Assets copiados correctamente de {assets_dir} -> {final_output_path}")      
   except Exception as e:
      logger.exception(f"Error copiando assets de {assets_dir} a {final_output_path}: {e}")
      return False  

   return True
def render_validation_report(
   port_report : dict[str,ValidationReport],
   report_metadata : dict[str,Any],
   match_report : dict,
   vessel_overlap : list,
   template_path : Path,
   output_path : Path,
   assets_dir : Path | None,
   conf : dict,
):
   env = Environment(
       loader=FileSystemLoader(str(template_path.parent)),
       autoescape=select_autoescape(["html", "j2"]),
   )
   template = env.get_template(template_path.name)

   ctx = _build_context(port_report,report_metadata, match_report,vessel_overlap, conf)
   html = template.render(**ctx)
   output_path.write_text(html, encoding="utf-8")
      
   if assets_dir is not None:
      copy_assets(assets_dir,output_path.parent)

__all__ = ['render_validation_report']

from reports.validation import render_validation_report
from pathlib import Path
from validations import ValidationReport
from validations.error_registry import ErrorType, WarningType

def test_render_report():
   template_path = Path('./templates/validation.html.j2')
   output_path = Path('./output/LINEUP_VALIDATION.html')
   assets_dir = Path('./templates/assets')
   bun_report = ValidationReport()
   bun_report.add_error('ejemplo',1,'ejemplo','nose','asdada' , error_type=ErrorType.INVALID_VALUE)
   bun_report.add_error('ejemplo',1,'ejemplo','nose','asdada' )
   bun_report.add_error('ejemplo',2,'ejemplo','nose','asdada' )
   bun_report.add_warning('ejemplo',1,'ejemplo','nose','asdada' )
   bun_report.add_warning('ejemplo',1,'ejemplo','nose','asdada' , warning_type=WarningType.SUSPICIOUS_VALUE)
   bun_report.issues_by_vessel_and_row()
   port_report = {'BUENAVENTURA':bun_report,'cartagena':bun_report}
   conf = {}
   report_metadata = {'total_rows':12,'total_ports': 5 }

   render_validation_report(port_report,report_metadata,template_path,output_path,assets_dir ,conf)


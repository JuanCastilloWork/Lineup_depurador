from pathlib import Path
from additional_data import LineUpValidationsData

def test_aditional_data():
   validations_data = LineUpValidationsData()
   validations_data.load(Path('./data/tables.xlsx'))
   print(validations_data.colombian_ports.loc[validations_data.colombian_ports.index == 'BUENAVEN'])   

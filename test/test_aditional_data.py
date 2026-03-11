from excel.aditional_data import AditionalDataManager
from pathlib import Path

def test_aditional_data():
   aditional_data = AditionalDataManager(Path('./data/tables.xlsx'),True)
   assert aditional_data.companies
   assert aditional_data.product_types
   assert aditional_data.port_terminals
   print(aditional_data.port_terminals)
   

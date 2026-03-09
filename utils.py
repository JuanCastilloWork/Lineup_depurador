from typing import Optional
import re
from datetime import date,datetime

def remove_multiple_white_spaces(value :  Optional[str])->Optional[str]:
   if value is None:
      return value
   value = re.sub(r'\s+',' ',str(value))
   return value.strip()

def remove_all_spaces(value : Optional[str])->Optional[str]:
   if value is None:
      return value
   return re.sub(r'\s+','',str(value)).replace(',','')
   

def parse_date(value: str | None | int | date | datetime) -> date | None:
   """Intenta parsear una fecha desde string o datetime de openpyxl."""
   if value is None:
      return None
   if isinstance(value, date):
      return value

   if isinstance(value,datetime):
      return value.date()

   if isinstance(value,str):
      return datetime.strptime(value,"%d/%m/%Y").date()

   if isinstance(value,int):
      raise ValueError('Estas recibiendo lamentablemente numero XD')



from decimal import Decimal,InvalidOperation
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from pydantic_core import PydanticCustomError
from enum import Enum
from datetime import date
from typing import Any
from constants import TypeEnum
import utils

class CompaniesModel(BaseModel):
   model_config = ConfigDict(
      str_to_upper=True
   )
   NAME : str
   IS_CHARTERER : bool
   IS_SHIPOWNER : bool
   IS_AGENCY : bool

   @field_validator('NAME',mode = 'before')
   def remove_white_spaces(v : Any):
      v = utils.remove_multiple_white_spaces(v)
      if not v:
         raise ValueError()
      return v

   @field_validator('IS_CHARTERER','IS_SHIPOWNER','IS_AGENCY',mode='before')
   def convert_to_bool(v : Any)->bool:
      if v:
         return True
      return False
   
class ProductModel(BaseModel):
   model_config = ConfigDict(
      str_to_upper=True
   )
   NAME : str
   TYPE :TypeEnum
   
   @field_validator( "TYPE", mode="before")
   @classmethod
   def normalize_enums(cls, v: str | None)->str | None:
      v = utils.remove_multiple_white_spaces(v)
      if v is None:
         return v
      return v.upper() if v is not None else v

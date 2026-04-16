import numpy as np
import pandas as pd
from decimal import Decimal, InvalidOperation
import re

def _to_decimal_scalar(val):
   if pd.isna(val):
      return pd.NA
   cleaned = re.sub(r'[^0-9.\-]', '', str(val))
   if not cleaned:
      return pd.NA
   try:
      return Decimal(cleaned)
   except InvalidOperation:
      return pd.NA

_to_decimal = np.frompyfunc(_to_decimal_scalar, 1, 1)

__all__ = ['_to_decimal']

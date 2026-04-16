import pandas as pd
from dataclasses import dataclass
from excel import layots

@dataclass
class OverlapConflict:
    vessel: str
    row_a: int
    row_b: int
    sheet_a: str
    sheet_b: str
    interval_a: tuple[int, int]
    interval_b: tuple[int, int]
    row_a_data: dict
    row_b_data: dict

def check_overlaps(
    df: pd.DataFrame,
    row_offset: int = 0,
) -> list[OverlapConflict]:
   conflicts = []

   vessel_col = layots.Columns.VESSEL
   ata_col    = layots.Columns.DATE_OF_ARRIVAL
   etc_col    = layots.Columns.ETC
   start_col  = '_DATE_OF_ARRIVAL_ORD'
   end_col    = '_ETC_ORD'
   sheet_col  = 'PORT'
   df_idx = '_IDX'

   for vessel, group in df[[vessel_col,ata_col,etc_col,start_col,end_col,sheet_col,df_idx]].groupby(vessel_col,dropna=False):
      valid = group.dropna(subset=[start_col]).sort_values(start_col)
      if len(valid) < 2:
         continue
      for i in range(1, len(valid)):
        prev = valid.iloc[i - 1]
        curr = valid.iloc[i]
        if curr[start_col] < prev[end_col]:
            conflicts.append(OverlapConflict(
                vessel=vessel,
                row_a=prev[df_idx] + row_offset,
                row_b=curr[df_idx] + row_offset,
                sheet_a=prev[sheet_col],
                sheet_b=curr[sheet_col],
                interval_a=(prev[start_col], prev[end_col]),
                interval_b=(curr[start_col], curr[end_col]),
                row_a_data={ata_col: prev[ata_col], etc_col: prev[etc_col]},
                row_b_data={ata_col: curr[ata_col], etc_col: curr[etc_col]},
            ))
   return conflicts

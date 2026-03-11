from dataclasses import dataclass
from datetime import date
from collections import defaultdict
from typing import TYPE_CHECKING
from models.lineup import LineUpBaseModel, PeriodEnum
import sys

@dataclass
class VesselInterval:
   vessel:   str
   row:      int          # fila Excel, para el ErrorRegistry
   start:    int          # half-day index (inclusivo)
   end:      int          # half-day index (inclusivo)
   doa:      date | None
   doa_p:    PeriodEnum | None
   etc:      date | None
   etc_p:    PeriodEnum | None
   sheet : str

def _to_half_day(d: date) -> int:
   """Convierte una fecha a su índice base (× 2)."""
   return d.toordinal() * 2

def _start_half(d: date | None, p: PeriodEnum | None) -> int | None:
   if d is None:
       return None
   base = _to_half_day(d)
   # conservador: None → AM (0), así ocupa desde el inicio del día
   return base + (1 if p == PeriodEnum.PM else 0)

def _end_half(d: date | None, p: PeriodEnum | None) -> int :
   if d is None:
       return sys.maxsize
   base = _to_half_day(d)
   # conservador: None → PM (1), así ocupa hasta el final del día
   return base + (0 if p == PeriodEnum.AM else 1)

def build_interval(row: int, model: LineUpBaseModel, sheet : str) -> VesselInterval | None:
   """
   Construye el intervalo DOA → ETC.
   Retorna None si no hay suficientes fechas para definirlo.
   """
   start = _start_half(model.DATE_OF_ARRIVAL, model.DATE_OF_ARRIVAL_PERIOD)

   if start is None:
       return None  # intervalo incompleto, no se puede verificar solapamiento

   end = _end_half(model.ETC, model.ETC_PERIOD)

   return VesselInterval(
       vessel=model.VESSEL,
       row=row,
       start=start,
       end=end,
       doa=model.DATE_OF_ARRIVAL,
       doa_p=model.DATE_OF_ARRIVAL_PERIOD,
       etc=model.ETC,
       etc_p=model.ETC_PERIOD,
       sheet = sheet
   )

# ---------- checker ----------

@dataclass
class OverlapConflict:
   vessel:   str
   row_a:    int
   row_b:    int
   interval_a: tuple[int, int]
   interval_b: tuple[int, int]
   row_a_data : dict[str, date | None | PeriodEnum]
   row_b_data : dict[str, date | None | PeriodEnum]
   sheet_a : str
   sheet_b : str

class OverlapChecker:
   """
   Acumula intervalos por barco y detecta solapamientos con sweep lineal.
   Un mismo VESSEL no puede tener dos intervalos que se crucen.
   """

   def __init__(self):
     # vessel → lista de intervalos, se mantiene ordenada por start
     self._intervals: dict[str, list[VesselInterval]] = defaultdict(list)

   def add(self, interval: VesselInterval) -> None:
      self._intervals[interval.vessel].append(interval)

   def check(self) -> list[OverlapConflict]:
      """
      Sweep lineal por VESSEL: ordena por start, luego compara cada intervalo
      contra el anterior. Si start_i <= end_{i-1} → solapamiento.
      O(n log n) por vessel.
      """
      conflicts: list[OverlapConflict] = []

      for vessel, intervals in self._intervals.items():
         sorted_ivs = sorted(intervals, key=lambda iv: (iv.start, iv.end))

         for i in range(1, len(sorted_ivs)):
            prev = sorted_ivs[i - 1]
            curr = sorted_ivs[i]

            # solapamiento: el actual empieza antes o cuando el anterior termina
            if curr.start < prev.end:
               conflicts.append(OverlapConflict(
                  vessel=vessel,
                  row_a=prev.row,
                  row_b=curr.row,
                  interval_a=(prev.start, prev.end),
                  interval_b=(curr.start, curr.end),
                  row_a_data={'doa':prev.doa,'etc':prev.etc ,'doa_p':prev.doa_p,'etc_p':prev.etc_p},
                  row_b_data={'doa':curr.doa,'etc':curr.etc ,'doa_p':curr.doa_p,'etc_p':curr.etc_p},
                  sheet_a = prev.sheet,
                  sheet_b =  curr.sheet
               )
            )

      return conflicts

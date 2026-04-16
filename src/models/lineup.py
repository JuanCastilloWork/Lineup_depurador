from decimal import Decimal,InvalidOperation
from pydantic import BaseModel, ConfigDict, field_validator, model_validator,ValidationInfo
from pydantic_core import PydanticCustomError
from enum import Enum
from datetime import date
from typing import Any
import utils
 
# ── Enums ─────────────────────────────────────────────────────────────────────
  
# ── Reglas de validación (constantes derivadas de los enums) ──────────────────
 
_PERIOD_ORDER = {PeriodEnum.AM: 0, PeriodEnum.PM: 1}
 
# Status que exigen ciertas fechas presentes
_STATUS_REQUIRES_ETB    = {StatusEnum.BERTHED}
_STATUS_REQUIRES_ETC    = {StatusEnum.SAILED}
_STATUS_NO_REQUIRES_ATA = {StatusEnum.ANNOUNCED}
_VALID_FUTURE_STATUSES  = {StatusEnum.ANNOUNCED}
 
# Status válidos por operación
_VALID_STATUS_OPERATIONS = {
    StatusEnum.ANNOUNCED:    {OperationEnum.TO_DISCHARGE, OperationEnum.TO_LOAD},
    StatusEnum.AT_LOAD_PORT: {OperationEnum.TO_DISCHARGE, OperationEnum.TO_LOAD, OperationEnum.TO_REPAIR},
    StatusEnum.DRIFTING:     {OperationEnum.TO_REPAIR, OperationEnum.TOWING},
    StatusEnum.SAILED:       {OperationEnum.LOADED, OperationEnum.DISCHARGED},
    StatusEnum.BERTHED: {
        OperationEnum.DISCHARGING,
        OperationEnum.DISCHARGED,
        OperationEnum.LOADING,
        OperationEnum.LOADED,
        OperationEnum.TO_REPAIR,
    },
}
 
# Campos que deben estar informados cuando el barco zarpa (SAILED).
# WINDOWS es el único campo del modelo que se permite vacío siempre.
_SAILED_REQUIRED_FIELDS: list[str] = [
    "PIER", "TERMINAL", "AGENCY", "CHARTERER",
    "SHIPOWNER", "PORT_LOAD_DISCH", "ETB", "ETC", "TYPE",
]
 
# Types en los que PRODUCT puede quedar vacío cuando SAILED,
# mapeado al valor de reemplazo que se usará en ese caso.
_SAILED_PRODUCT_OPTIONAL_TYPES: dict[TypeEnum, str] = {
    TypeEnum.STEEL:         "STEEL",
    TypeEnum.FERTILIZERS:   "FERTILIZERS",
    TypeEnum.PROJECT_CARGO: "GENERAL CARGO",
}
 
 
# ── Helpers ───────────────────────────────────────────────────────────────────
 
def _period_exceeds(p1: PeriodEnum | None, p2: PeriodEnum | None) -> bool:
    """True solo si AMBOS son conocidos y p1 > p2."""
    if p1 is None or p2 is None:
        return False
    return _PERIOD_ORDER[p1] > _PERIOD_ORDER[p2]
 
 
# ── Modelo ────────────────────────────────────────────────────────────────────


class LineUpBaseModel(BaseModel):
   model_config = ConfigDict(
      str_to_upper=True
   )

   VESSEL:    str
   PIER:      str | None
   TERMINAL:  str | None
   AGENCY:    str | None
   CHARTERER: str | None
   SHIPOWNER: str | None
   PRODUCT:   str | None
   PORT_LOAD_DISCH :  str | None
   WINDOWS : str | None # Unico campo siempre opcional (es de tolu no me voy a poner a revisar especificamente eso)

   # Listas cerradas
   STATUS:    StatusEnum
   OPERATION: OperationEnum
   TYPE:      TypeEnum | None = None  # puede ser None

   # Fechas
   DATE_OF_ARRIVAL: date | None
   DATE_OF_ARRIVAL_PERIOD: PeriodEnum | None

   ETB: date | None
   ETB_PERIOD: PeriodEnum | None

   ETC: date | None
   ETC_PERIOD: PeriodEnum | None

   # Cantidades
   MT_BY_PRODUCT: str | None
   TOTAL_MT: Decimal | None

   # ------------------------------------------------------------------
   # Field validators
   # ------------------------------------------------------------------

   @field_validator("VESSEL", mode="before")
   @classmethod
   def vessel_not_empty(cls, v: str | None) -> str:
      """VESSEL es obligatorio y no puede quedar vacío tras strip."""
      cleaned = utils.remove_multiple_white_spaces(v)
      if not cleaned:
         raise ValueError("VESSEL no puede estar vacío o ser solo espacios.")
      return cleaned

   @field_validator("PIER", "TERMINAL", "AGENCY","CHARTERER", "SHIPOWNER", "PRODUCT", "WINDOWS", mode="before")
   @classmethod
   def remove_white_spaces(cls, v : str | None)->str | None:
      return utils.remove_multiple_white_spaces(v)

   @field_validator("MT_BY_PRODUCT", mode='before')
   @classmethod
   def normalize_mt_by_product(cls, v : str | None)->str | None:
      cleaned =  utils.remove_all_spaces(v)
      return cleaned.replace(',','') if cleaned else None

   @field_validator("TOTAL_MT", mode="before")
   @classmethod
   def parse_decimal(cls, v):
       if v is None:
           return None
       try:
           return Decimal(str(v))    # str(v) evita imprecisiones de float
       except InvalidOperation:
           raise ValueError(f"No se puede convertir a Decimal: {v!r}")   

   @field_validator("DATE_OF_ARRIVAL", "ETB", "ETC", mode="before")
   @classmethod
   def parse_dates(cls, v: str | int | None | date) -> date | None:
      return utils.parse_date(v)

   @field_validator("STATUS", "OPERATION", "TYPE", "DATE_OF_ARRIVAL_PERIOD","ETB_PERIOD","ETC_PERIOD", mode="before")
   @classmethod
   def normalize_enums(cls, v: str | None)->str | None:
      v = utils.remove_multiple_white_spaces(v)
      if v is None:
         return v
      return v.upper() if v is not None else v

   # ------------------------------------------------------------------
   # Model validators (orden: primero fechas, luego status, luego MT)
   # ------------------------------------------------------------------

   @model_validator(mode='after')
   def validate_dates(self) -> 'LineUpBaseModel':
      doa, etb, etc = self.DATE_OF_ARRIVAL, self.ETB, self.ETC   
      doa_p, etb_p, etc_p = self.DATE_OF_ARRIVAL_PERIOD, self.ETB_PERIOD, self.ETC_PERIOD       
   
      if doa is None and etb is None and etc is None:
         return self

      if doa is not None and etb is not None:
         if doa > etb:
            raise PydanticCustomError(
                'date_order_violation',
                'DATE_OF_ARRIVAL ({DATE_OF_ARRIVAL}) no puede ser posterior a ETB ({ETB}).',
                {'fields': ['DATE_OF_ARRIVAL', 'ETB'],
                 'values': {'DATE_OF_ARRIVAL': str(doa), 'ETB': str(etb)}}
            )
         if doa == etb and _period_exceeds(doa_p, etb_p):
            raise PydanticCustomError(
                'date_order_violation',
                'DATE_OF_ARRIVAL ({DATE_OF_ARRIVAL}) y ETB ({ETB}) son el mismo día pero '
                'DATE_OF_ARRIVAL_PERIOD ({DATE_OF_ARRIVAL_PERIOD}) es posterior a ETB_PERIOD ({ETB_PERIOD}).',
                {'fields': ['DATE_OF_ARRIVAL_PERIOD', 'ETB_PERIOD'],
                 'values': {'DATE_OF_ARRIVAL': str(doa), 'ETB': str(etb),
                            'DATE_OF_ARRIVAL_PERIOD': doa_p, 'ETB_PERIOD': etb_p}}
            )   
      # DOA vs ETC
      if doa is not None and etc is not None:
         if doa > etc:
            raise PydanticCustomError(
               'date_order_violation',
               'DATE_OF_ARRIVAL ({DATE_OF_ARRIVAL}) no puede ser posterior a ETC ({ETC}).',
               {'fields': ['DATE_OF_ARRIVAL', 'ETC'],
                'values': {'DATE_OF_ARRIVAL': str(doa), 'ETC': str(etc)}}
            )
         if doa == etc and _period_exceeds(doa_p, etc_p):
            raise PydanticCustomError(
               'date_order_violation',
               'DATE_OF_ARRIVAL ({DATE_OF_ARRIVAL}) y ETC ({ETC}) son el mismo día pero '
               'DATE_OF_ARRIVAL_PERIOD ({DATE_OF_ARRIVAL_PERIOD}) es posterior a ETC_PERIOD ({ETC_PERIOD}).',
               {'fields': ['DATE_OF_ARRIVAL_PERIOD', 'ETC_PERIOD'],
                'values': {'DATE_OF_ARRIVAL': str(doa), 'ETC': str(etc),
                             'DATE_OF_ARRIVAL_PERIOD': doa_p, 'ETC_PERIOD': etc_p}}
            )

      # ETB vs ETC
      if etb is not None and etc is not None:
         if etb > etc:
            raise PydanticCustomError(
               'date_order_violation',
               'ETB ({ETB}) no puede ser posterior a ETC ({ETC}).',
               {'fields': ['ETB', 'ETC'],
                'values': {'ETB': str(etb), 'ETC': str(etc)}}
            )
         if etb == etc and _period_exceeds(etb_p, etc_p):
            raise PydanticCustomError(
            'date_order_violation',
            'ETB ({ETB}) y ETC ({ETC}) son el mismo día pero '
            'ETB_PERIOD ({ETB_PERIOD}) es posterior a ETC_PERIOD ({ETC_PERIOD}).',
            {'fields': ['ETB_PERIOD', 'ETC_PERIOD'],
             'values': {'ETB': str(etb), 'ETC': str(etc),
                        'ETB_PERIOD': etb_p, 'ETC_PERIOD': etc_p}}
            )

      return self

   
   # ── Model Validators 2: Terminales, Productos y Cantidades ────────────────
 
   @model_validator(mode="after")
   def validate_terminal(self, info: ValidationInfo) -> "LineUpBaseModel":
       if self.TERMINAL is None:
           return self
       context = info.context or {}
       available_terminals = context.get("available_terminals")
       if available_terminals and self.TERMINAL not in available_terminals:
           raise PydanticCustomError(
               "invalid_terminal",
               "TERMINAL '{terminal}' no está en la lista de terminales disponibles: {available}.",
               {"fields": ["TERMINAL"],
                "values": {"terminal": self.TERMINAL, "available": list(available_terminals)}},
           )
       return self

   @model_validator(mode="after")
   def validate_products(self, info: ValidationInfo) -> "LineUpBaseModel":
       if self.PRODUCT is None:
           return self
       context = info.context or {}
       if not self.TYPE:
           raise PydanticCustomError(
               "product_requires_type",
               "Se informó PRODUCT ({PRODUCT}) pero TYPE es None. TYPE es obligatorio cuando se indica PRODUCT.",
               {"fields": ["PRODUCT", "TYPE"],
                "values": {"PRODUCT": self.PRODUCT, "TYPE": None}},
           )
       products = self.PRODUCT.split("/")
       available_products = context.get("available_products", {}).get(self.TYPE, [])
       for product in products:
           if available_products and product not in available_products:
               raise PydanticCustomError(
                   "invalid_product",
                   "PRODUCT ({PRODUCT}) no está en la lista de productos disponibles para TYPE ({TYPE}): ({available_products}).",
                   {"fields": ["PRODUCT", "TYPE"],
                    "values": {"PRODUCT": product, "TYPE": self.TYPE,
                               "available_products": list(available_products)}},
               )
       return self    

   @model_validator(mode="after")
   def validate_mt_totals(self) -> "LineUpBaseModel":
       mt_by_product = self.MT_BY_PRODUCT
       total_mt      = self.TOTAL_MT
 
       if mt_by_product is None and total_mt is None:
           return self
 
       if mt_by_product is None and total_mt is not None:
           raise PydanticCustomError(
               "mt_mismatch",
               "MT_BY_PRODUCT es None pero TOTAL_MT tiene valor ({total_mt}).",
               {"fields": ["MT_BY_PRODUCT", "TOTAL_MT"],
                "values": {"MT_BY_PRODUCT": None, "TOTAL_MT": str(total_mt)}},
           )
       if mt_by_product is not None and total_mt is None:
           raise PydanticCustomError(
               "mt_mismatch",
               "TOTAL_MT es None pero MT_BY_PRODUCT tiene valor ({mt_by_product}).",
               {"fields": ["MT_BY_PRODUCT", "TOTAL_MT"],
                "values": {"MT_BY_PRODUCT": mt_by_product, "TOTAL_MT": None}},
           )
       if total_mt < 0 or total_mt > Decimal("300000"):
           raise PydanticCustomError(
               "mt_out_of_range",
               "TOTAL_MT fuera de rango válido: {total_mt}.",
               {"fields": ["TOTAL_MT"], "values": {"TOTAL_MT": str(total_mt)}},
           )
 
       parts = mt_by_product.split("/")
       try:
           parsed = [Decimal(p.strip()) for p in parts if p.strip()]
       except Exception:
           raise PydanticCustomError(
               "mt_parse_error",
               "MT_BY_PRODUCT contiene valores no numéricos: '{mt_by_product}'.",
               {"fields": ["MT_BY_PRODUCT"], "values": {"MT_BY_PRODUCT": mt_by_product}},
           )
       if not parsed:
           raise PydanticCustomError(
               "mt_parse_error",
               "MT_BY_PRODUCT está vacío tras el split.",
               {"fields": ["MT_BY_PRODUCT"], "values": {"MT_BY_PRODUCT": mt_by_product}},
           )
 
       computed_sum = sum(parsed)
       if computed_sum != total_mt:
           raise PydanticCustomError(
               "mt_sum_mismatch",
               "La suma de MT_BY_PRODUCT ({computed_sum}) no coincide con TOTAL_MT ({total_mt}).",
               {"fields": ["MT_BY_PRODUCT", "TOTAL_MT"],
                "values": {"MT_BY_PRODUCT": mt_by_product, "TOTAL_MT": str(total_mt),
                           "computed_sum": str(computed_sum)}},
           )
 
       if self.PRODUCT and len(parts) > 1:
           if len(self.PRODUCT.split("/")) != len(parts):
               raise PydanticCustomError(
                   "mt_products_mismatch",
                   "No hay la misma cantidad de productos ({prod_cantidad}) y cantidades ({mt_cantidad}).",
                   {"fields": ["PRODUCT", "MT_BY_PRODUCT"],
                    "values": {"prod_cantidad": len(self.PRODUCT.split("/")), "mt_cantidad": len(parts)}},
               )
 
       return self

   
   @model_validator(mode='after')
   def validate_status_dates(self) -> 'LineUpBaseModel':
       if self.DATE_OF_ARRIVAL is None and self.STATUS not in _STATUS_NO_REQUIRES_ATA:
           raise PydanticCustomError(
               'status_requires_date',
               "STATUS='{STATUS}' requiere que ATA esté informado.",
               {'fields': ['STATUS', 'DATE_OF_ARRIVAL'], 'values': {'STATUS': self.STATUS.value, 'DATE_OF_ARRIVAL': None}}
           )
       if self.STATUS in _STATUS_REQUIRES_ETB and self.ETB is None:
           raise PydanticCustomError(
               'status_requires_date',
               "STATUS='{STATUS}' requiere que ETB esté informado.",
               {'fields': ['STATUS', 'ETB'], 'values': {'STATUS': self.STATUS.value, 'ETB': None}}
           )
       if self.STATUS in _STATUS_REQUIRES_ETC and self.ETC is None:
           raise PydanticCustomError(
               'status_requires_date',
               "STATUS='{STATUS}' requiere que ETC esté informado.",
               {'fields': ['STATUS', 'ETC'], 'values': {'STATUS': self.STATUS.value, 'ETC': None}}
           )
       return self   
   
   @model_validator(mode='after')
   def validate_status_vs_today(self) -> 'LineUpBaseModel':
      doa = self.DATE_OF_ARRIVAL
      if doa is None:
          return self
   
      today = date.today()
   
      if doa < today and self.STATUS == StatusEnum.ANNOUNCED:
         raise PydanticCustomError(
             'status_date_mismatch',
             'DATE_OF_ARRIVAL ({DATE_OF_ARRIVAL}) es anterior a hoy ({today}) pero STATUS sigue siendo {STATUS}.',
             {'fields': ['DATE_OF_ARRIVAL', 'STATUS'], 'values': {'DATE_OF_ARRIVAL': str(doa), 'STATUS': self.STATUS.value, 'today': str(today)}}
         )
      if doa > today and self.STATUS not in _VALID_FUTURE_STATUSES:
         raise PydanticCustomError(
             'status_date_mismatch',
             "DATE_OF_ARRIVAL ({DATE_OF_ARRIVAL}) es posterior a hoy ({today}) con estado {STATUS}. Barcos futuros solo pueden tener: {valid}.",
             {'fields': ['DATE_OF_ARRIVAL', 'STATUS'], 'values': {'DATE_OF_ARRIVAL': str(doa), 'STATUS': self.STATUS.value, 'today': str(today), 'valid': [s.value for s in _VALID_FUTURE_STATUSES]}}
         )
      return self
      
   @model_validator(mode='after')
   def validate_status_vs_operation(self) -> 'LineUpBaseModel':
       if self.STATUS not in _VALID_STATUS_OPERATIONS:
           return self
   
       valid_operations = _VALID_STATUS_OPERATIONS[self.STATUS]
       if self.OPERATION not in valid_operations:
           raise PydanticCustomError(
               'invalid_operation_for_status',
               "STATUS='{STATUS}' tiene una operación inválida '{OPERATION}'. Válidas: {valid}.",
               {'fields': ['STATUS', 'OPERATION'], 'values': {'STATUS': self.STATUS.value, 'OPERATION': self.OPERATION.value, 'valid_operations': [o.value for o in valid_operations]}}
           )
       return self

   @model_validator(mode = 'after')
   def validate_sailed(self)-> 'LineUpBaseModel':
      if self.STATUS != StatusEnum.SAILED:
         return self

      missing = [f for f in _SAILED_REQUIRED_FIELDS if getattr(self, f) is None]
      if missing:
         raise PydanticCustomError(
            "sailed_missing_fields",
            "STATUS=SAILED requiere que los siguientes campos estén informados: {missing}.",
            {"fields": missing, "values": {"missing": missing}},
         )

      assert self.TYPE is not None
      
      # 2. PRODUCT: coerción o error según TYPE
      if self.PRODUCT is None:
          if self.TYPE in _SAILED_PRODUCT_OPTIONAL_TYPES:
              # Coerción: rellenamos con el valor de reemplazo
              self.PRODUCT = _SAILED_PRODUCT_OPTIONAL_TYPES[self.TYPE]
          else:
              raise PydanticCustomError(
                  "sailed_missing_fields",
                  "STATUS=SAILED con TYPE='{TYPE}' requiere que PRODUCT esté informado.",
                  {"fields": ["PRODUCT"],
                   "values": {"TYPE": self.TYPE.value if self.TYPE else None}},
              )

      # 3. MT siempre obligatorio al zarpar
      if self.MT_BY_PRODUCT is None or self.TOTAL_MT is None:
          missing_mt = [f for f in ("MT_BY_PRODUCT", "TOTAL_MT") if getattr(self, f) is None]
          raise PydanticCustomError(
              "sailed_missing_fields",
              "STATUS=SAILED requiere que las cantidades estén informadas. Faltan: {missing}.",
              {"fields": missing_mt, "values": {"missing": missing_mt}},
          )      
            
      return self   
   
   def to_client_report(self) -> dict[str, Any]:
      
      MONTH_ABBR = {
          1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
          5: "MAY", 6: "JUN", 7: "JUL", 8: "AUG",
          9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC"
      }
      
      def fmt_date(d: date | None, period: PeriodEnum | None) -> str:
          if d is None:
              return "TBC"
          base = f"{d.day} - {MONTH_ABBR[d.month].lower()}"
          if period is not None:
              # "AM" -> "A M", "PM" -> "P M"
              spaced = " ".join(period.value).lower()
              return f"{base} {spaced}"
          return base

      
      def fmt_pier(value: str | None) -> int | str:
          if value is None:
              return "TBC"
          try:
              return int(value)
          except (ValueError, TypeError):
              return value
      
      def fmt_mt_by_product(value: str | None) -> str:
          if value is None:
              return "TBC"
          
          def fmt_number(s: str) -> str:
              try:
                  # Con decimales
                  if "." in s:
                      return f"{Decimal(s):,}"
                  # Entero
                  return f"{int(s):,}"
              except (ValueError, InvalidOperation):
                  return s  # si no es número, lo deja como está
          
          # Detecta si tiene slashes (múltiples valores)
          if "/" in value:
              parts = value.split("/")
              return " / ".join(fmt_number(p) for p in parts)
          
          return fmt_number(value)
            
      def fmt(value) -> Any:
          if value is None:
              return "TBC"
          if isinstance(value, Enum):
              return value.value
          if isinstance(value, Decimal):
              return value  # o str(value) si querés
          return value

      return {
          "VESSEL":           fmt(self.VESSEL),
          "PIER":             fmt_pier(self.PIER),
          "TERMINAL":         fmt(self.TERMINAL),
          "AGENCY":           fmt(self.AGENCY),
          "CHARTERER":        fmt(self.CHARTERER),
          "SHIPOWNER":        fmt(self.SHIPOWNER),
          "PRODUCT":          fmt(self.PRODUCT),
          "PORT_LOAD_DISCH":  fmt(self.PORT_LOAD_DISCH),
          "WINDOWS":          fmt(self.WINDOWS),
          "STATUS":           fmt(self.STATUS),
          "OPERATION":        fmt(self.OPERATION),
          "TYPE":             fmt(self.TYPE),
          "DATE_OF_ARRIVAL":  fmt_date(self.DATE_OF_ARRIVAL, self.DATE_OF_ARRIVAL_PERIOD),
          "ETB":              fmt_date(self.ETB, self.ETB_PERIOD),
          "ETC":              fmt_date(self.ETC, self.ETC_PERIOD),
          "MT_BY_PRODUCT":    fmt_mt_by_product(self.MT_BY_PRODUCT),
          "TOTAL_MT":         fmt(self.TOTAL_MT),
      }

from enum import Enum

class CargoType(str, Enum):
   CLINKER_CEMENT  = "CLINKER/CEMENT"
   COAL            = "COAL" 
   CRUDE           = "CRUDE"
   DRY_PRODUCTS    = "DRY PRODUCTS"
   EDIBLE_OIL      = "EDIBLE OIL"
   FERTILIZERS     = "FERTILIZERS"
   GRAINS          = "GRAINS"
   LIQUID_CHEMS    = "LIQUID/CHEMS"
   LIVESTOCK       = "LIVESTOCK"
   OTHERS          = "OTHERS"
   PROJECT_CARGO   = "PROJECT CARGO"
   STEEL           = "STEEL"

class VesselStatus(str, Enum):
   ANCHORED     = "ANCHORED"
   ANNOUNCED    = "ANNOUNCED"
   AT_LOAD_PORT = "AT LOAD PORT"
   BERTHED      = "BERTHED"
   DRIFTING     = "DRIFTING"
   SAILED       = "SAILED"
 
class OperationStatus(str, Enum):
   TO_DISCHARGE = "TO DISCHARGE"
   DISCHARGING  = "DISCHARGING"
   DISCHARGED   = "DISCHARGED"
   TO_LOAD      = "TO LOAD"
   LOADING      = "LOADING"
   LOADED       = "LOADED"
   TO_REPAIR    = "TO REPAIR"
   TOWING       = "TOWING"
 
class DatePeriod(str,Enum):
   AM = "AM"
   PM = "PM"


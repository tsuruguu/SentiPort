from pydantic import BaseModel
from typing import Optional
import uuid

class VesselBase(BaseModel):
    imo_number: str
    current_vessel_name: str
    year_built: Optional[int] = None
    flag_country_id: Optional[int] = None
    vessel_type_id: Optional[int] = None

class VesselResponse(VesselBase):
    vessel_id: uuid.UUID

    class Config:
        from_attributes = True
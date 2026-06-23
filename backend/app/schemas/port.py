from pydantic import BaseModel
from typing import Optional
import uuid

class PortBase(BaseModel):
    un_locode: str
    port_name: str
    max_draft_meters: Optional[float] = None
    has_icebreaker_support: bool = False
    has_cold_storage_facility: bool = False

class PortResponse(PortBase):
    port_id: uuid.UUID

    class Config:
        from_attributes = True

class BerthResponse(BaseModel):
    berth_id: uuid.UUID
    port_id: uuid.UUID
    berth_code: str
    berth_name: Optional[str] = None
    max_draft_meters: Optional[float] = None
    supports_dangerous_goods: bool = False
    supports_reefer_containers: bool = False

    class Config:
        from_attributes = True
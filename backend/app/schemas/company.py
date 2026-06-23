from pydantic import BaseModel
from typing import Optional
import uuid

class CompanyBase(BaseModel):
    company_name: str
    imo_company_number: Optional[str] = None
    primary_contact_email: Optional[str] = None
    ownership_transparency_flag: bool = True
    is_sanctioned: bool = False

class CompanyResponse(CompanyBase):
    company_id: uuid.UUID

    class Config:
        from_attributes = True
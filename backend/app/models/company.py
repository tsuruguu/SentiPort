import uuid
from sqlalchemy import Column, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base

class Company(Base):
    __tablename__ = "companies"
    __table_args__ = {"schema": "port_intel"}  # KLUCZOWE!

    company_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = Column(String(250), nullable=False)
    imo_company_number = Column(String(7), unique=True)
    primary_contact_email = Column(String(200))
    ownership_transparency_flag = Column(Boolean, default=True)
    is_sanctioned = Column(Boolean, default=False)
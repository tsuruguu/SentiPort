import uuid
from sqlalchemy import Column, String, Boolean, SmallInteger, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.models.base import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = {"schema": "port_intel"}  # KLUCZOWE!

    company_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imo_company_number = Column(String(7), unique=True)
    company_name = Column(String(250), nullable=False)
    country_id = Column(SmallInteger)
    registered_address = Column(Text)
    primary_contact_name = Column(String(150))
    primary_contact_email = Column(String(200))
    primary_contact_phone = Column(String(50))

    # Czy struktura własności jest przejrzysta - wpływa na risk score
    ownership_transparency_flag = Column(Boolean, default=True, nullable=False)
    is_sanctioned = Column(Boolean, default=False, nullable=False)  # cache, źródło prawdy: sanctions_screening_results
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class CompanyContact(Base):
    """Osoby kontaktowe w firmach armatorskich/operatorskich."""
    __tablename__ = "company_contacts"
    __table_args__ = {"schema": "port_intel"}

    contact_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    job_title = Column(String(150))
    email = Column(String(200))
    phone = Column(String(50))
    is_primary_for_nominations = Column(Boolean, default=False, nullable=False)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
import uuid
from sqlalchemy import Column, String, Integer, SmallInteger, Boolean, Date, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.sql import func
from app.models.base import Base
from app.models.enums import VesselDomain


class Vessel(Base):
    __tablename__ = "vessels"
    __table_args__ = {"schema": "port_intel"}  # KLUCZOWE!

    vessel_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imo_number = Column(String(7), unique=True, nullable=False)
    mmsi = Column(String(9))
    call_sign = Column(String(15))
    current_vessel_name = Column(String(200), nullable=False)
    domain = Column(SQLEnum(VesselDomain, name="vessel_domain", schema="port_intel", create_type=False),
                     default=VesselDomain.unknown, nullable=False)
    year_built = Column(SmallInteger)

    # Na hakatonie upraszczamy: trzymamy płaskie ID-ki do słowników,
    # żeby nie walczyć z cyklicznymi importami w relacjach SQLAlchemy.
    flag_country_id = Column(SmallInteger)
    vessel_type_id = Column(SmallInteger)
    classification_society_id = Column(SmallInteger)

    is_active = Column(Boolean, default=True, nullable=False)  # FALSE = wycofany/zezłomowany
    scrapped_date = Column(Date)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
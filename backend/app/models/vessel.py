import uuid
from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base


class Vessel(Base):
    __tablename__ = "vessels"
    __table_args__ = {"schema": "port_intel"}  # KLUCZOWE!

    vessel_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imo_number = Column(String(7), unique=True, nullable=False)
    current_vessel_name = Column(String(200), nullable=False)
    year_built = Column(Integer)

    # Na hakatonie upraszczamy: trzymamy płaskie ID-ki do słowników,
    # żeby nie walczyć z cyklicznymi importami w relacjach SQLAlchemy.
    flag_country_id = Column(Integer)
    vessel_type_id = Column(Integer)
import uuid
from sqlalchemy import Column, String, Boolean, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.models.base import Base


class Port(Base):
    __tablename__ = "ports"
    __table_args__ = {"schema": "port_intel"}

    port_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    un_locode = Column(String(5), unique=True, nullable=False)
    port_name = Column(String(200), nullable=False)

    # Obsługa danych geoprzestrzennych z PostGIS
    location = Column(Geography(geometry_type='POINT', srid=4326))

    max_draft_meters = Column(Numeric(5, 2))
    has_icebreaker_support = Column(Boolean, default=False)
    has_cold_storage_facility = Column(Boolean, default=False)


class Berth(Base):
    """Nabrzeża w porcie"""
    __tablename__ = "berths"
    __table_args__ = {"schema": "port_intel"}

    berth_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    port_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.ports.port_id", ondelete="CASCADE"), nullable=False)
    berth_code = Column(String(50), nullable=False)
    berth_name = Column(String(200))
    max_draft_meters = Column(Numeric(5, 2))

    # Pola kluczowe do logiki decyzyjnej
    supports_dangerous_goods = Column(Boolean, default=False)
    supports_reefer_containers = Column(Boolean, default=False)  # Ważne dla ładunków chłodniczych!
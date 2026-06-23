import uuid
from sqlalchemy import Column, String, Boolean, Numeric, SmallInteger, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from geoalchemy2 import Geography
from app.models.base import Base


class Country(Base):
    __tablename__ = "countries"
    __table_args__ = {"schema": "port_intel"}

    country_id = Column(SmallInteger, primary_key=True)
    iso_alpha2 = Column(String(2), unique=True, nullable=False)
    iso_alpha3 = Column(String(3), unique=True, nullable=False)
    country_name = Column(String(150), nullable=False)
    paris_mou_flag_tier = Column(String(15))
    is_eu_member = Column(Boolean, default=False, nullable=False)
    is_sanctioned_jurisdiction = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class Port(Base):
    __tablename__ = "ports"
    __table_args__ = {"schema": "port_intel"}

    port_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    un_locode = Column(String(5), unique=True, nullable=False)
    port_name = Column(String(200), nullable=False)
    country_id = Column(SmallInteger)

    # Obsługa danych geoprzestrzennych z PostGIS
    location = Column(Geography(geometry_type='POINT', srid=4326))
    timezone = Column(String(64), default="UTC", nullable=False)

    max_draft_meters = Column(Numeric(5, 2))
    max_loa_meters = Column(Numeric(6, 2))
    max_beam_meters = Column(Numeric(5, 2))
    has_icebreaker_support = Column(Boolean, default=False)
    has_cold_storage_facility = Column(Boolean, default=False)
    is_isps_compliant = Column(Boolean, default=True, nullable=False)

    port_authority_name = Column(String(200))
    port_authority_contact_email = Column(String(200))
    port_authority_contact_phone = Column(String(50))
    notes = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class Berth(Base):
    """Nabrzeża w porcie"""
    __tablename__ = "berths"
    __table_args__ = {"schema": "port_intel"}

    berth_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    port_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.ports.port_id", ondelete="CASCADE"), nullable=False)
    berth_code = Column(String(50), nullable=False)
    berth_name = Column(String(200))
    location = Column(Geography(geometry_type='POINT', srid=4326))

    max_draft_meters = Column(Numeric(5, 2))
    max_loa_meters = Column(Numeric(6, 2))
    max_dwt_tonnes = Column(Numeric(10, 2))

    # Pola kluczowe do logiki decyzyjnej
    supports_dangerous_goods = Column(Boolean, default=False, nullable=False)
    supports_reefer_containers = Column(Boolean, default=False, nullable=False)  # Ważne dla ładunków chłodniczych!
    supports_ro_ro = Column(Boolean, default=False, nullable=False)
    has_shore_power = Column(Boolean, default=False, nullable=False)
    crane_capacity_tonnes = Column(Numeric(8, 2))

    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
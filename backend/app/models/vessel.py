import uuid
from sqlalchemy import Column, String, Integer, SmallInteger, Boolean, Date, DateTime, Text, Numeric, ForeignKey
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


class VesselTechnicalSpecs(Base):
    """
    Wersjonowane dane techniczne statku (wymiary, tonaż, klasa lodowa).
    Często wspominane przez armatora już w mailu nominacyjnym (LOA, draft,
    DWT, TEU) - kluczowe dla doboru bezpiecznego nabrzeża (Krok 3).
    """
    __tablename__ = "vessel_technical_specs"
    __table_args__ = {"schema": "port_intel"}

    spec_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.vessels.vessel_id", ondelete="CASCADE"),
                        nullable=False)

    length_overall_meters = Column(Numeric(6, 2))   # LOA
    beam_meters = Column(Numeric(5, 2))               # szerokość
    draft_meters = Column(Numeric(5, 2))              # zanurzenie
    air_draft_meters = Column(Numeric(5, 2))          # wysokość nad linią wodną (mosty!)
    gross_tonnage = Column(Numeric(10, 2))            # GT
    net_tonnage = Column(Numeric(10, 2))              # NT
    deadweight_tonnage = Column(Numeric(10, 2))       # DWT
    main_engine_power_kw = Column(Numeric(10, 2))
    max_speed_knots = Column(Numeric(4, 1))
    has_ice_class = Column(Boolean, default=False, nullable=False)
    ice_class_designation = Column(String(50))        # np. 'PC6', '1A Super'
    container_capacity_teu = Column(Integer)          # jeśli kontenerowiec
    has_reefer_plugs = Column(Boolean, default=False, nullable=False)
    reefer_plug_count = Column(Integer)

    effective_from = Column(Date, server_default=func.current_date(), nullable=False)
    effective_until = Column(Date)
    data_source = Column(String(150))  # np. 'email_nomination', 'VesselFinder', 'manual'

    created_at = Column(DateTime(timezone=True), server_default=func.now())
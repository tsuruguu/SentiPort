import uuid
from sqlalchemy import Column, String, Integer, SmallInteger, Boolean, Date, DateTime, Text, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.sql import func
from app.models.base import Base
from app.models.enums import VesselDomain, CompanyRoleType, SanctionsListSource, SanctionsScreeningResult as \
    SanctionsScreeningResultEnum


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


class VesselNameHistory(Base):
    """Historia nazw i flag statku - zmiana nazwy/flagi bywa sygnałem
    ryzyka ('flag hopping')."""
    __tablename__ = "vessel_name_history"
    __table_args__ = {"schema": "port_intel"}

    name_history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.vessels.vessel_id", ondelete="CASCADE"),
                       nullable=False)
    vessel_name = Column(String(200), nullable=False)
    flag_country_id = Column(SmallInteger)
    effective_from = Column(Date, nullable=False)
    effective_until = Column(Date)
    source = Column(String(100))  # np. 'IMO GISIS', 'manual_entry'

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VesselCompanyRole(Base):
    """Relacja statek<->firma z rolą (armator rejestrowy, operator,
    manager techniczny, P&I club...) - armator rejestrowy MOŻE SIĘ
    różnić od operatora handlowego, który faktycznie wysyła nominację."""
    __tablename__ = "vessel_company_roles"
    __table_args__ = {"schema": "port_intel"}

    role_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.vessels.vessel_id", ondelete="CASCADE"),
                       nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.companies.company_id", ondelete="CASCADE"),
                        nullable=False)
    role_type = Column(SQLEnum(CompanyRoleType, name="company_role_type", schema="port_intel", create_type=False),
                       nullable=False)
    effective_from = Column(Date, server_default=func.current_date(), nullable=False)
    effective_until = Column(Date)
    is_current = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VesselCertificate(Base):
    """Certyfikaty statku - ISM, ISPS (ISSC), klasa, itp."""
    __tablename__ = "vessel_certificates"
    __table_args__ = {"schema": "port_intel"}

    certificate_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.vessels.vessel_id", ondelete="CASCADE"),
                       nullable=False)
    certificate_type = Column(String(100), nullable=False)  # np. 'ISM Safety Management Certificate'
    certificate_number = Column(String(100))
    issuing_authority = Column(String(200))
    issue_date = Column(Date)
    expiry_date = Column(Date)
    document_file_url = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class PSCInspection(Base):
    """Historia inspekcji Port State Control - liczba usterek i
    zatrzymań to empirycznie zweryfikowane predyktory ryzyka."""
    __tablename__ = "psc_inspections"
    __table_args__ = {"schema": "port_intel"}

    inspection_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.vessels.vessel_id", ondelete="CASCADE"),
                       nullable=False)
    inspecting_port_id = Column(UUID(as_uuid=True))
    inspecting_authority = Column(String(200))  # np. 'Paris MoU', 'Tokyo MoU'
    inspection_date = Column(Date, nullable=False)
    deficiency_count = Column(Integer, default=0, nullable=False)
    was_detained = Column(Boolean, default=False, nullable=False)
    detention_days = Column(Integer)
    inspection_report_url = Column(Text)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PSCDeficiency(Base):
    """Pojedyncza usterka znaleziona przy konkretnej inspekcji PSC."""
    __tablename__ = "psc_deficiencies"
    __table_args__ = {"schema": "port_intel"}

    deficiency_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inspection_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.psc_inspections.inspection_id",
                                                            ondelete="CASCADE"), nullable=False)
    deficiency_code = Column(String(20))  # harmonizowany kod (Paris MoU code list)
    deficiency_description = Column(Text, nullable=False)
    severity = Column(String(20))  # 'low' | 'medium' | 'high' | 'detainable'
    action_taken = Column(String(100))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SanctionsScreening(Base):
    """Wynik przeglądu sankcyjnego (OFAC/UE/UK) per statek lub firma.
    Insert-only, dla pełnego audytu."""
    __tablename__ = "sanctions_screening_results"
    __table_args__ = {"schema": "port_intel"}

    screening_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.vessels.vessel_id", ondelete="CASCADE"))
    company_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.companies.company_id", ondelete="CASCADE"))
    list_source = Column(SQLEnum(SanctionsListSource, name="sanctions_list_source", schema="port_intel",
                                  create_type=False), nullable=False)
    screening_result = Column(SQLEnum(SanctionsScreeningResultEnum, name="sanctions_screening_result",
                                       schema="port_intel", create_type=False), nullable=False)
    matched_entry_name = Column(String(250))
    match_confidence_pct = Column(Numeric(5, 2))
    screened_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_by_user = Column(String(150))
    review_notes = Column(Text)
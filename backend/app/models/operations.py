import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Boolean, Numeric, SmallInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.sql import func
from app.models.base import Base
from app.models.enums import NominationStatus, ImdgHazardClass, PortServiceType, ServiceOrderStatus


class Nomination(Base):
    __tablename__ = "nominations"
    __table_args__ = {"schema": "port_intel"}

    nomination_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.vessels.vessel_id"), nullable=False)
    nominating_company_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.companies.company_id"), nullable=False)
    nominating_contact_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.company_contacts.contact_id"))
    destination_port_id = Column(UUID(as_uuid=True), nullable=False)
    email_hash = Column(String, unique=True, index=True, nullable=True)

    status = Column(SQLEnum(NominationStatus, name="nomination_status", schema="port_intel", create_type=False),
                    default=NominationStatus.received)

    eta = Column(DateTime(timezone=True))
    etd = Column(DateTime(timezone=True))
    requested_berth_id = Column(UUID(as_uuid=True))  # nabrzeże, o które poprosił armator w mailu
    assigned_berth_id = Column(UUID(as_uuid=True))   # nabrzeże faktycznie przydzielone przez system

    # Surowa treść maila - zachowana w całości dla audytu i ponownego parsowania
    source_email_subject = Column(String(500))
    source_email_body_raw = Column(Text)
    source_email_received_at = Column(DateTime(timezone=True))
    source_email_sender_address = Column(String(200))

    # Pole na ekstrakcję LLM/agenta - "resztki", których parser nie złapał
    # w sztywne kolumny, trafiają tutaj (np. {"model": ..., "confidence": ...})
    llm_extraction_metadata = Column(JSONB)
    assigned_agent_name = Column(String(150))
    mentor_contact_note = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class NominationUnstructuredNote(Base):
    __tablename__ = "nomination_unstructured_notes"
    __table_args__ = {"schema": "port_intel"}

    note_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nomination_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.nominations.nomination_id", ondelete="CASCADE"),
                           nullable=False)
    note_text = Column(Text, nullable=False)
    extracted_by = Column(String(50), default='llm')
    confidence_score = Column(Numeric(4, 2))
    requires_human_review = Column(Boolean, default=True)
    reviewed_at = Column(DateTime(timezone=True))
    reviewed_by = Column(String(150))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CargoManifest(Base):
    __tablename__ = "cargo_manifests"
    __table_args__ = {"schema": "port_intel"}

    cargo_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nomination_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.nominations.nomination_id", ondelete="CASCADE"))
    port_call_id = Column(UUID(as_uuid=True))
    cargo_description = Column(String(300), nullable=False)
    cargo_quantity = Column(Numeric(12, 2))
    cargo_unit = Column(String(20))
    imdg_hazard_class = Column(
        SQLEnum(ImdgHazardClass, name="imdg_hazard_class", schema="port_intel", create_type=False),
        default=ImdgHazardClass.none)
    un_number = Column(String(10))  # UN number dla towarów niebezpiecznych (np. UN1203)
    requires_refrigeration = Column(Boolean, default=False)
    target_temperature_celsius = Column(Numeric(5, 2))
    is_perishable = Column(Boolean, default=False)
    origin_country_id = Column(SmallInteger)
    destination_country_id = Column(SmallInteger)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PortServiceOrder(Base):
    """
    Zamówienie usługi portowej (pilotaż, holowniki, prąd z lądu, lekarz,
    barber, bunkrowanie, zmiana załogi, itd.).

    Armator często prosi o te usługi już w mailu nominacyjnym, ZANIM
    istnieje port_call (ten powstaje dopiero po weryfikacji nominacji).
    Dlatego zamówienie może być powiązane albo z konkretną wizytą
    (port_call_id), albo - tymczasowo - z samą nominacją (nomination_id).
    Przynajmniej jedno z dwóch musi być wypełnione (chk_service_order_parent
    w bazie).
    """
    __tablename__ = "port_service_orders"
    __table_args__ = {"schema": "port_intel"}

    service_order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    port_call_id = Column(UUID(as_uuid=True))
    nomination_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.nominations.nomination_id", ondelete="CASCADE"))
    service_type = Column(SQLEnum(PortServiceType, name="port_service_type", schema="port_intel", create_type=False),
                          nullable=False)
    provider_company_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.companies.company_id"))
    status = Column(SQLEnum(ServiceOrderStatus, name="service_order_status", schema="port_intel", create_type=False),
                    default=ServiceOrderStatus.requested)

    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    scheduled_for = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    cost_amount = Column(Numeric(12, 2))
    cost_currency = Column(String(3))
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
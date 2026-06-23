import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Enum as SQLEnum
from app.models.base import Base
from app.models.enums import NominationStatus, ImdgHazardClass


class Nomination(Base):
    __tablename__ = "nominations"
    __table_args__ = {"schema": "port_intel"}

    nomination_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.vessels.vessel_id"), nullable=False)
    nominating_company_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.companies.company_id"), nullable=False)
    destination_port_id = Column(UUID(as_uuid=True), nullable=False)

    status = Column(SQLEnum(NominationStatus, name="nomination_status", schema="port_intel", create_type=False),
                    default=NominationStatus.received)

    eta = Column(DateTime(timezone=True))
    etd = Column(DateTime(timezone=True))
    assigned_berth_id = Column(UUID(as_uuid=True))

    source_email_subject = Column(String(500))
    source_email_body_raw = Column(Text)

    llm_extraction_metadata = Column(JSONB)
    assigned_agent_name = Column(String(150))


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


class CargoManifest(Base):
    __tablename__ = "cargo_manifests"
    __table_args__ = {"schema": "port_intel"}

    cargo_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nomination_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.nominations.nomination_id", ondelete="CASCADE"))
    cargo_description = Column(String(300), nullable=False)
    cargo_quantity = Column(Numeric(12, 2))
    cargo_unit = Column(String(20))
    imdg_hazard_class = Column(
        SQLEnum(ImdgHazardClass, name="imdg_hazard_class", schema="port_intel", create_type=False),
        default=ImdgHazardClass.none)
    requires_refrigeration = Column(Boolean, default=False)
    is_perishable = Column(Boolean, default=False)
import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Enum as SQLEnum
from app.models.base import Base
from app.models.enums import NominationStatus


class Nomination(Base):
    __tablename__ = "nominations"
    __table_args__ = {"schema": "port_intel"}

    nomination_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.vessels.vessel_id"), nullable=False)
    nominating_company_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.companies.company_id"), nullable=False)
    destination_port_id = Column(UUID(as_uuid=True), nullable=False)

    # Parametr create_type=False mówi ORM-owi: "Użyj enuma, który już istnieje w bazie"
    status = Column(SQLEnum(NominationStatus, name="nomination_status", schema="port_intel", create_type=False),
                    default=NominationStatus.received)

    source_email_subject = Column(String(500))
    source_email_body_raw = Column(Text)

    # To pole uratuje wam życie na demo - LLM wrzuci tu wszystko, czego nie zmapuje na sztywne kolumny
    llm_extraction_metadata = Column(JSONB)
    assigned_agent_name = Column(String(150))
import uuid
from sqlalchemy import Column, String, Numeric, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SQLEnum
from app.models.base import Base
from app.models.enums import RiskTier


class VesselRiskAssessment(Base):
    __tablename__ = "vessel_risk_assessments"
    __table_args__ = {"schema": "port_intel"}

    assessment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vessel_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.vessels.vessel_id", ondelete="CASCADE"),
                       nullable=False)

    # Powiązanie z konkretnym mailem (nominacją), jeśli na jego podstawie zrobiono ocenę
    nomination_id = Column(UUID(as_uuid=True), ForeignKey("port_intel.nominations.nomination_id"))

    overall_risk_score = Column(Numeric(5, 2), nullable=False)

    # Mapowanie Enum - schema i name MUSZĄ się zgadzać z Twoim sql
    risk_tier = Column(SQLEnum(RiskTier, name="risk_tier", schema="port_intel", create_type=False), nullable=False)

    assessment_trigger = Column(String(100))  # np. 'new_nomination', 'manual_review'
    is_current = Column(Boolean, default=True)  # Najważniejsza flaga - pobieramy tylko te, gdzie = True
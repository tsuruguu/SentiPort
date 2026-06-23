from pydantic import BaseModel
from typing import Optional
import uuid
from app.models.enums import RiskTier

class RiskAssessmentBase(BaseModel):
    overall_risk_score: float
    risk_tier: RiskTier
    assessment_trigger: Optional[str] = None
    is_current: bool = True

class RiskAssessmentResponse(RiskAssessmentBase):
    assessment_id: uuid.UUID
    vessel_id: uuid.UUID
    nomination_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True
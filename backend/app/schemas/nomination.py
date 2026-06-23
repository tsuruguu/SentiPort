from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
from app.models.enums import NominationStatus

# To odbieramy z frontendu / Postmana
class EmailPayload(BaseModel):
    subject: str
    body: str
    sender_email: str

# To zwracamy jako odpowiedź
class NominationResponse(BaseModel):
    nomination_id: uuid.UUID
    status: NominationStatus
    source_email_subject: Optional[str]
    assigned_agent_name: Optional[str]
    llm_extraction_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

from app.models.enums import DocumentType, DocumentStatus


class GeneratedDocumentResponse(BaseModel):
    document_id: uuid.UUID
    nomination_id: Optional[uuid.UUID] = None
    document_type: DocumentType
    status: DocumentStatus
    version_number: int
    filename: Optional[str] = None
    file_hash_sha256: Optional[str] = None
    generated_by: Optional[str] = None
    generated_at: datetime

    class Config:
        from_attributes = True
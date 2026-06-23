from fastapi import APIRouter
from app.schemas.common import MessageResponse

router = APIRouter()

@router.post("/generate", response_model=MessageResponse)
def generate_port_documents():
    """Generuje paczkę PDFów (ISPS, Cargo Declaration) do wysyłki do kapitanatu."""
    # Tu w przyszłości podepniemy app.services.document_service
    return {"message": "Dokumenty PDF wygenerowane i zapisane na S3 (mock)."}
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Any
import uuid

from app.api import deps
from app.schemas.document import GeneratedDocumentResponse
from app.repositories import document_repository
from app.services import document_service

router = APIRouter()


@router.post("/nominations/{nomination_id}/generate", response_model=GeneratedDocumentResponse,
            status_code=status.HTTP_201_CREATED)
def generate_nomination_document(
        nomination_id: uuid.UUID,
        db: Session = Depends(deps.get_db),
) -> Any:
    """
    Generuje realny PDF "Pakietu Nominacyjnego" dla danej nominacji
    (FUN-007/FUN-008/FUN-010) - statek, firma, port, ładunek, usługi
    portowe i sekcja statusu weryfikacji (QUA-001/QUA-002/QUA-005:
    pewność ekstrakcji AI, pola brakujące, notatki do przeglądu - nigdy
    ukrywane).

    Dokument NIE jest formalnym zgłoszeniem do kapitanatu portu - to
    pakiet roboczy do przeglądu przez agenta portowego. Każde
    wywołanie tworzy nową wersję (version_number), poprzednie wersje
    nie są usuwane (pełny audyt).
    """
    return document_service.generate_port_entry_notification(db, nomination_id)


@router.get("/nominations/{nomination_id}/documents", response_model=list[GeneratedDocumentResponse])
def list_nomination_documents(
        nomination_id: uuid.UUID,
        db: Session = Depends(deps.get_db),
) -> Any:
    """Lista wszystkich wygenerowanych dokumentów (wszystkich wersji) dla danej nominacji."""
    return document_repository.get_documents_for_nomination(db, nomination_id)


@router.get("/{document_id}/download")
def download_document(
        document_id: uuid.UUID,
        db: Session = Depends(deps.get_db),
) -> Response:
    """Pobiera surową treść wygenerowanego dokumentu PDF."""
    document = document_repository.get_document_by_id(db, document_id)
    if not document or not document.file_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dokument nie istnieje")

    return Response(
        content=bytes(document.file_data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{document.filename or "dokument.pdf"}"'},
    )
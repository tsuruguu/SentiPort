"""
Generowanie dokumentów dla kapitanatu portu (FUN-010, QUA-005).

Zastępuje poprzedni mock - to jest teraz prawdziwy serwis: składa dane
nominacji (przez nomination_view_service, ten sam widok co w UI), renderuje
PDF (pdf_export_service), zapisuje go w bazie (document_repository) i
zwraca metadane + identyfikator do pobrania.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError
from app.models.enums import DocumentType
from app.repositories import document_repository, nomination_repository
from app.services import nomination_view_service, pdf_export_service


def generate_port_entry_notification(db: Session, nomination_id: uuid.UUID, generated_by: str = "system_auto"):
    """
    Generuje realny PDF "Pakietu Nominacyjnego" dla danej nominacji,
    zapisuje go w bazie (jako kolejną wersję, jeśli już istniał wcześniej
    dokument tego typu dla tej nominacji) i zwraca wiersz GeneratedDocument
    gotowy do zwrócenia w odpowiedzi API / pobrania.
    """
    nomination_detail = nomination_view_service.get_nomination_detail(db, nomination_id)
    if not nomination_detail:
        raise EntityNotFoundError(entity_name="Nomination", entity_id=nomination_id)

    pdf_bytes = pdf_export_service.generate_nomination_pdf(nomination_detail)
    file_hash = pdf_export_service.compute_file_hash(pdf_bytes)

    vessel_name = nomination_detail.vessel.current_vessel_name if nomination_detail.vessel else "statek_nieznany"
    safe_name = vessel_name.replace(" ", "_").replace("/", "-")
    filename = f"pakiet_nominacyjny_{safe_name}_{str(nomination_id)[:8]}.pdf"

    return document_repository.save_generated_document(
        db,
        nomination_id=nomination_id,
        document_type=DocumentType.port_entry_notification,
        filename=filename,
        file_data=pdf_bytes,
        file_hash_sha256=file_hash,
        generated_by=generated_by,
    )
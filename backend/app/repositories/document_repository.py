from sqlalchemy.orm import Session
from app.models.operations import GeneratedDocument
from app.models.enums import DocumentType, DocumentStatus
import uuid


def save_generated_document(
        db: Session,
        nomination_id: uuid.UUID,
        document_type: DocumentType,
        filename: str,
        file_data: bytes,
        file_hash_sha256: str,
        generated_by: str = "system_auto",
) -> GeneratedDocument:
    """
    Zapisuje nowo wygenerowany PDF. Jeśli dla tej nominacji istnieją już
    wcześniejsze wersje tego samego typu dokumentu, nowa wersja dostaje
    kolejny `version_number` - poprzednia NIE jest usuwana (audyt: pełna
    historia wersji dokumentu, zgodnie z duchem insert-only stosowanym
    w innych tabelach audytowych tej bazy, np. vessel_risk_assessments).
    """
    previous_versions = db.query(GeneratedDocument).filter(
        GeneratedDocument.nomination_id == nomination_id,
        GeneratedDocument.document_type == document_type,
    ).count()

    document = GeneratedDocument(
        nomination_id=nomination_id,
        document_type=document_type,
        status=DocumentStatus.generated,
        version_number=previous_versions + 1,
        filename=filename,
        file_data=file_data,
        file_hash_sha256=file_hash_sha256,
        generated_by=generated_by,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def get_document_by_id(db: Session, document_id: uuid.UUID) -> GeneratedDocument | None:
    return db.query(GeneratedDocument).filter(GeneratedDocument.document_id == document_id).first()


def get_documents_for_nomination(db: Session, nomination_id: uuid.UUID) -> list[GeneratedDocument]:
    return db.query(GeneratedDocument).filter(
        GeneratedDocument.nomination_id == nomination_id
    ).order_by(GeneratedDocument.generated_at.desc()).all()
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.models.operations import Nomination
from app.models.vessel import VesselTechnicalSpecs
from app.repositories import nomination_repository, vessel_repository, port_repository, company_repository
from app.schemas.nomination_detail import (
    NominationListItemResponse, NominationListResponse, NominationDetailResponse,
    VesselSummary, VesselTechnicalSpecsResponse, CompanySummary, ContactSummary,
    PortSummary, BerthSummary, CargoItemResponse, AttachmentResponse,
    UnstructuredNoteResponse, RequestedServiceResponse,
)
from app.models.enums import NominationStatus


def _vessel_summary(db: Session, vessel_id: Optional[uuid.UUID]) -> Optional[VesselSummary]:
    if not vessel_id:
        return None
    vessel = vessel_repository.get_vessel_by_id(db, vessel_id)
    return VesselSummary.model_validate(vessel) if vessel else None


def _company_summary(db: Session, company_id: Optional[uuid.UUID]) -> Optional[CompanySummary]:
    if not company_id:
        return None
    company = company_repository.get_company_by_id(db, company_id)
    return CompanySummary.model_validate(company) if company else None


def _contact_summary(db: Session, contact_id: Optional[uuid.UUID]) -> Optional[ContactSummary]:
    if not contact_id:
        return None
    contact = company_repository.get_contact_by_id(db, contact_id)
    return ContactSummary.model_validate(contact) if contact else None


def _port_summary(db: Session, port_id: Optional[uuid.UUID]) -> Optional[PortSummary]:
    if not port_id:
        return None
    port = port_repository.get_port_by_id(db, port_id)
    return PortSummary.model_validate(port) if port else None


def _berth_summary(db: Session, berth_id: Optional[uuid.UUID]) -> Optional[BerthSummary]:
    if not berth_id:
        return None
    berth = port_repository.get_berth_by_id(db, berth_id)
    return BerthSummary.model_validate(berth) if berth else None


def build_list_item(db: Session, nomination: Nomination) -> NominationListItemResponse:
    """
    Składa lekki widok listy - dociąga tylko podsumowania (nazwa statku,
    firmy, portu), bez treści maila czy szczegółów ładunku.
    """
    notes = nomination_repository.get_unstructured_notes(db, nomination.nomination_id)
    requires_review = any(note.requires_human_review and not note.reviewed_at for note in notes)

    metadata = nomination.llm_extraction_metadata or {}

    return NominationListItemResponse(
        nomination_id=nomination.nomination_id,
        status=nomination.status,
        source_email_subject=nomination.source_email_subject,
        source_email_sender_address=nomination.source_email_sender_address,
        source_email_received_at=nomination.source_email_received_at,
        eta=nomination.eta,
        etd=nomination.etd,
        vessel=_vessel_summary(db, nomination.vessel_id),
        nominating_company=_company_summary(db, nomination.nominating_company_id),
        destination_port=_port_summary(db, nomination.destination_port_id),
        confidence_score=metadata.get("confidence"),
        requires_human_review=requires_review,
        created_at=nomination.created_at,
    )


def list_nominations(
        db: Session,
        status: Optional[NominationStatus] = None,
        limit: int = 50,
        offset: int = 0,
) -> NominationListResponse:
    nominations = nomination_repository.list_nominations(db, status=status, limit=limit, offset=offset)
    total = nomination_repository.count_nominations(db, status=status)

    return NominationListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[build_list_item(db, nom) for nom in nominations],
    )


def get_nomination_detail(db: Session, nomination_id: uuid.UUID) -> Optional[NominationDetailResponse]:
    """
    Składa pełny widok szczegółów jednej nominacji - dociąga statek
    (+ jego najnowsze dane techniczne), firmę, kontakt, port, oba
    nabrzeża (żądane/przydzielone), cargo, usługi, notatki i załączniki.
    """
    nomination = nomination_repository.get_nomination(db, nomination_id)
    if not nomination:
        return None

    # Najnowsze dane techniczne statku (jeśli jest kilka wersji w czasie,
    # bierzemy ostatnio dodaną - effective_until IS NULL = aktualna).
    technical_specs = None
    if nomination.vessel_id:
        specs_row = db.query(VesselTechnicalSpecs).filter(
            VesselTechnicalSpecs.vessel_id == nomination.vessel_id
        ).order_by(VesselTechnicalSpecs.created_at.desc()).first()
        if specs_row:
            technical_specs = VesselTechnicalSpecsResponse.model_validate(specs_row)

    cargo_items = [
        CargoItemResponse.model_validate(c)
        for c in nomination_repository.get_cargo_items(db, nomination_id)
    ]
    requested_services = [
        RequestedServiceResponse.model_validate(s)
        for s in nomination_repository.get_requested_services(db, nomination_id)
    ]
    unstructured_notes = [
        UnstructuredNoteResponse.model_validate(n)
        for n in nomination_repository.get_unstructured_notes(db, nomination_id)
    ]
    attachments = [
        AttachmentResponse.model_validate(a)
        for a in nomination_repository.get_attachments(db, nomination_id)
    ]

    metadata = nomination.llm_extraction_metadata or {}

    return NominationDetailResponse(
        nomination_id=nomination.nomination_id,
        status=nomination.status,
        vessel=_vessel_summary(db, nomination.vessel_id),
        vessel_technical_specs=technical_specs,
        nominating_company=_company_summary(db, nomination.nominating_company_id),
        nominating_contact=_contact_summary(db, nomination.nominating_contact_id),
        destination_port=_port_summary(db, nomination.destination_port_id),
        requested_berth=_berth_summary(db, nomination.requested_berth_id),
        assigned_berth=_berth_summary(db, nomination.assigned_berth_id),
        eta=nomination.eta,
        etd=nomination.etd,
        cargo_items=cargo_items,
        requested_services=requested_services,
        unstructured_notes=unstructured_notes,
        attachments=attachments,
        source_email_subject=nomination.source_email_subject,
        source_email_body_raw=nomination.source_email_body_raw,
        source_email_sender_address=nomination.source_email_sender_address,
        source_email_received_at=nomination.source_email_received_at,
        confidence_score=metadata.get("confidence"),
        fields_missing=metadata.get("fields_missing", []),
        extraction_model=metadata.get("model"),
        assigned_agent_name=nomination.assigned_agent_name,
        created_at=nomination.created_at,
        updated_at=nomination.updated_at,
    )
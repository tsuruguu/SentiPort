from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from app.models.enums import NominationStatus, ImdgHazardClass, PortServiceType, ServiceOrderStatus


# ---------------------------------------------------------------------------
# Bloki zagnieżdżone - wspólne dla widoku listy i szczegółów
# ---------------------------------------------------------------------------

class VesselSummary(BaseModel):
    vessel_id: uuid.UUID
    imo_number: str
    current_vessel_name: str
    year_built: Optional[int] = None

    class Config:
        from_attributes = True


class VesselTechnicalSpecsResponse(BaseModel):
    length_overall_meters: Optional[float] = None
    beam_meters: Optional[float] = None
    draft_meters: Optional[float] = None
    air_draft_meters: Optional[float] = None
    gross_tonnage: Optional[float] = None
    net_tonnage: Optional[float] = None
    deadweight_tonnage: Optional[float] = None
    max_speed_knots: Optional[float] = None
    has_ice_class: bool = False
    ice_class_designation: Optional[str] = None
    container_capacity_teu: Optional[int] = None
    has_reefer_plugs: bool = False
    reefer_plug_count: Optional[int] = None
    data_source: Optional[str] = None

    class Config:
        from_attributes = True


class CompanySummary(BaseModel):
    company_id: uuid.UUID
    company_name: str
    is_sanctioned: bool = False

    class Config:
        from_attributes = True


class ContactSummary(BaseModel):
    contact_id: uuid.UUID
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None

    class Config:
        from_attributes = True


class PortSummary(BaseModel):
    port_id: uuid.UUID
    un_locode: str
    port_name: str

    class Config:
        from_attributes = True


class BerthSummary(BaseModel):
    berth_id: uuid.UUID
    berth_code: str
    berth_name: Optional[str] = None

    class Config:
        from_attributes = True


class BerthRecommendationResponse(BaseModel):
    """Jedno nabrzeże spośród TOP-N rekomendacji, z wynikiem i powodami
    (do wyświetlenia agentowi portowemu jako wyjaśnienie 'czemu to nabrzeże')."""
    berth: BerthSummary
    score: float
    reasons: List[str] = []

    class Config:
        from_attributes = True


class BerthRecommendationListResponse(BaseModel):
    nomination_id: uuid.UUID
    recommendations: List[BerthRecommendationResponse]
    warning: Optional[str] = None  # np. gdy lista jest krótsza niż żądana liczba (brak bezpiecznych nabrzeży)


class CargoItemResponse(BaseModel):
    cargo_id: uuid.UUID
    cargo_description: str
    cargo_quantity: Optional[float] = None
    cargo_unit: Optional[str] = None
    imdg_hazard_class: ImdgHazardClass
    un_number: Optional[str] = None
    requires_refrigeration: bool = False
    target_temperature_celsius: Optional[float] = None
    is_perishable: bool = False

    class Config:
        from_attributes = True


class AttachmentResponse(BaseModel):
    """
    Metadane załącznika - NIE zawiera samej treści pliku (file_data).
    Treść pliku pobiera się osobno przez
    GET /nominations/{id}/attachments/{attachment_id}/download
    """
    attachment_id: uuid.UUID
    filename: str
    content_type: str
    file_size_bytes: int
    sent_to_agent_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UnstructuredNoteResponse(BaseModel):
    note_id: uuid.UUID
    note_text: str
    extracted_by: str
    confidence_score: Optional[float] = None
    requires_human_review: bool = True
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None

    class Config:
        from_attributes = True


class RequestedServiceResponse(BaseModel):
    service_order_id: uuid.UUID
    service_type: PortServiceType
    status: ServiceOrderStatus
    notes: Optional[str] = None
    scheduled_for: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Lekki widok listy - bez ciężkich pól (treść maila, surowa odpowiedź agenta),
# żeby GET /nominations było szybkie nawet z wieloma wierszami.
# ---------------------------------------------------------------------------

class NominationListItemResponse(BaseModel):
    nomination_id: uuid.UUID
    status: NominationStatus
    source_email_subject: Optional[str] = None
    source_email_sender_address: Optional[str] = None
    source_email_received_at: Optional[datetime] = None
    eta: Optional[datetime] = None
    etd: Optional[datetime] = None
    vessel: Optional[VesselSummary] = None
    nominating_company: Optional[CompanySummary] = None
    destination_port: Optional[PortSummary] = None
    confidence_score: Optional[float] = None
    requires_human_review: bool = False  # True jeśli istnieją niezweryfikowane unstructured_notes
    created_at: datetime

    class Config:
        from_attributes = True


class NominationListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[NominationListItemResponse]


# ---------------------------------------------------------------------------
# Żądania akcji agenta portowego (zapis decyzji po przeglądzie nominacji)
# ---------------------------------------------------------------------------

class AssignBerthRequest(BaseModel):
    """berth_id=None czyści przypisanie nabrzeża."""
    berth_id: Optional[uuid.UUID] = None


class ChangeStatusRequest(BaseModel):
    status: NominationStatus


class UpdateNominationFieldsRequest(BaseModel):
    """
    Tylko podane pola są aktualizowane (częściowy update). Wszystkie
    nullable - wysyłaj tylko to, co faktycznie chcesz poprawić.
    Pola poza tą listą (np. źródłowa treść maila) nie są edytowalne
    przez ten endpoint.
    """
    vessel_id: Optional[uuid.UUID] = None
    nominating_company_id: Optional[uuid.UUID] = None
    nominating_contact_id: Optional[uuid.UUID] = None
    destination_port_id: Optional[uuid.UUID] = None
    requested_berth_id: Optional[uuid.UUID] = None
    eta: Optional[datetime] = None
    etd: Optional[datetime] = None
    assigned_agent_name: Optional[str] = None
    mentor_contact_note: Optional[str] = None

    def to_update_dict(self) -> dict:
        """Zwraca tylko pola, które faktycznie zostały podane (nie None) -
        żeby PATCH nie czyścił pól, których agent nie chciał zmieniać."""
        return self.model_dump(exclude_unset=True)


# ---------------------------------------------------------------------------
# Pełny widok szczegółów - jedna nominacja ze wszystkim, czego UI
# potrzebuje do wyświetlenia karty przeglądu/weryfikacji.
# ---------------------------------------------------------------------------

class NominationDetailResponse(BaseModel):
    nomination_id: uuid.UUID
    status: NominationStatus

    # Statek
    vessel: Optional[VesselSummary] = None
    vessel_technical_specs: Optional[VesselTechnicalSpecsResponse] = None

    # Strony
    nominating_company: Optional[CompanySummary] = None
    nominating_contact: Optional[ContactSummary] = None

    # Port i nabrzeża
    destination_port: Optional[PortSummary] = None
    requested_berth: Optional[BerthSummary] = None  # o co poprosił armator
    assigned_berth: Optional[BerthSummary] = None   # co przydzielił system (Krok 3)

    # Terminy
    eta: Optional[datetime] = None
    etd: Optional[datetime] = None

    # Ładunek, usługi, notatki, załączniki
    cargo_items: List[CargoItemResponse] = []
    requested_services: List[RequestedServiceResponse] = []
    unstructured_notes: List[UnstructuredNoteResponse] = []
    attachments: List[AttachmentResponse] = []

    # Mail źródłowy (pełna treść - OK dla widoku szczegółów, w przeciwieństwie do listy)
    source_email_subject: Optional[str] = None
    source_email_body_raw: Optional[str] = None
    source_email_sender_address: Optional[str] = None
    source_email_received_at: Optional[datetime] = None

    # Metadane ekstrakcji
    confidence_score: Optional[float] = None
    fields_missing: List[str] = []
    extraction_model: Optional[str] = None
    assigned_agent_name: Optional[str] = None

    created_at: datetime
    updated_at: datetime
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ---------------------------------------------------------------------------
# To, co WYSYŁAMY do agenta (kolegi) - wyłącznie dane, które realnie mamy
# z samego maila (treść + metadane), bez żadnego zgadywania.
# ---------------------------------------------------------------------------

class EmailForExtraction(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    sender_address: Optional[str] = None
    received_at: Optional[datetime] = None


class AgentExtractionRequest(BaseModel):
    nomination_id: str
    email: EmailForExtraction


# ---------------------------------------------------------------------------
# To, co agent ODSYŁA do nas. Każde pole nullable - agent zwraca null,
# jeśli czegoś nie znalazł w treści maila, zamiast zgadywać.
# ---------------------------------------------------------------------------

class ExtractedVessel(BaseModel):
    imo_number: Optional[str] = None
    name: Optional[str] = None


class ExtractedContact(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None


class ExtractedCargo(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    imdg_hazard_class: Optional[str] = None  # musi być jedną z wartości ImdgHazardClass
    un_number: Optional[str] = None
    requires_refrigeration: Optional[bool] = None
    target_temperature_celsius: Optional[float] = None
    is_perishable: Optional[bool] = None
    origin_country: Optional[str] = None       # kod ISO alpha-2, np. "PL"
    destination_country: Optional[str] = None  # kod ISO alpha-2, np. "PL"


class AgentExtractionResponse(BaseModel):
    vessel: Optional[ExtractedVessel] = None
    port_locode: Optional[str] = None
    eta: Optional[datetime] = None
    etd: Optional[datetime] = None
    requested_berth_name: Optional[str] = None
    nominating_company_name: Optional[str] = None
    nominating_contact: Optional[ExtractedContact] = None
    cargo: Optional[ExtractedCargo] = None
    unstructured_notes: List[str] = []
    confidence_score: Optional[float] = None
    fields_missing: List[str] = []
    extraction_model: Optional[str] = None
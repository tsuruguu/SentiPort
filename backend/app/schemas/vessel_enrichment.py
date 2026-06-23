from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime
import uuid


# ---------------------------------------------------------------------------
# Co WYSYŁAMY do agenta wzbogacenia (drugi, osobny agent ElevenLabs) -
# "wszystko, co mamy o tym statku w bazie", scalone w jeden JSON ≤50kB.
# ---------------------------------------------------------------------------

class VesselIdentitySnapshot(BaseModel):
    imo_number: str
    current_name: str
    mmsi: Optional[str] = None
    call_sign: Optional[str] = None
    year_built: Optional[int] = None
    is_active: bool = True


class NameHistoryEntry(BaseModel):
    vessel_name: str
    flag_country_iso: Optional[str] = None
    effective_from: Optional[date] = None
    effective_until: Optional[date] = None


class TechnicalSpecsSnapshot(BaseModel):
    length_overall_meters: Optional[float] = None
    draft_meters: Optional[float] = None
    deadweight_tonnage: Optional[float] = None
    container_capacity_teu: Optional[int] = None
    has_ice_class: bool = False
    effective_from: Optional[date] = None
    data_source: Optional[str] = None


class CompanyRoleEntry(BaseModel):
    company_name: str
    role_type: str
    is_current: bool = True


class CertificateEntry(BaseModel):
    certificate_type: str
    expiry_date: Optional[date] = None
    is_expired: Optional[bool] = None


class PSCDeficiencySummary(BaseModel):
    severity: Optional[str] = None
    description: str


class PSCInspectionEntry(BaseModel):
    inspection_date: date
    inspecting_authority: Optional[str] = None
    deficiency_count: int = 0
    was_detained: bool = False
    deficiencies: List[PSCDeficiencySummary] = []


class SanctionsScreeningEntry(BaseModel):
    list_source: str
    screening_result: str
    screened_at: Optional[datetime] = None


class PreviousCargoSummary(BaseModel):
    description: str
    imdg_hazard_class: str = "none"
    requires_refrigeration: bool = False


class PreviousNominationEntry(BaseModel):
    nomination_id: str
    status: str
    eta: Optional[datetime] = None
    port_name: Optional[str] = None
    cargo: List[PreviousCargoSummary] = []


class VesselHistoryPayload(BaseModel):
    """
    Pełny kontrakt wysyłany do agenta wzbogacenia. Budowany progresywnie
    z możliwością obcinania sekcji historycznych, jeśli serializacja
    przekroczy limit 50kB (patrz vessel_history_enrichment_service.py).
    """
    nomination_id: str
    vessel: VesselIdentitySnapshot
    name_history: List[NameHistoryEntry] = []
    technical_specs_history: List[TechnicalSpecsSnapshot] = []
    company_roles: List[CompanyRoleEntry] = []
    certificates: List[CertificateEntry] = []
    psc_inspections: List[PSCInspectionEntry] = []
    sanctions_screenings: List[SanctionsScreeningEntry] = []
    current_risk_score: Optional[float] = None
    current_risk_tier: Optional[str] = None
    previous_nominations: List[PreviousNominationEntry] = []
    truncated_sections: List[str] = []  # jawna informacja dla agenta, co zostało obcięte z powodu limitu 50kB


# ---------------------------------------------------------------------------
# Co ODBIERAMY od agenta wzbogacenia - propozycja konfiguracji + lista
# niespójności/braków, o które port powinien dopytać armatora.
# ---------------------------------------------------------------------------

class ProposedConfigField(BaseModel):
    """Jedno proponowane pole konfiguracji statku w porcie. is_inferred
    odróżnia 'agent uzupełnił coś, czego nie było w mailu' (pokazywane
    na żółto w UI) od 'agent tylko potwierdził to, co już mieliśmy'."""
    field_name: str
    proposed_value: Optional[str] = None
    is_inferred: bool = False  # True = uzupełnienie brakujących danych (UI: żółte pole)
    confidence: Optional[float] = None
    source_note: Optional[str] = None  # np. "na podstawie poprzedniej wizyty z 2026-03-01"


class DataInconsistency(BaseModel):
    """Niespójność lub brak danych, o który port powinien dopytać armatora."""
    field_name: str
    description: str
    severity: str = "medium"  # 'low' | 'medium' | 'high'


class VesselEnrichmentResponse(BaseModel):
    proposed_configuration: List[ProposedConfigField] = []
    inconsistencies_to_clarify: List[DataInconsistency] = []
    summary_note: Optional[str] = None
    confidence_score: Optional[float] = None
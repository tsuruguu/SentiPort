from sqlalchemy.orm import Session
from app.models.vessel import (
    Vessel, VesselTechnicalSpecs, VesselNameHistory, VesselCompanyRole,
    VesselCertificate, PSCInspection, PSCDeficiency, SanctionsScreening,
)
from app.models.operations import Nomination, CargoManifest
from app.models.risk import VesselRiskAssessment
import uuid

def get_vessel_by_id(db: Session, vessel_id: uuid.UUID) -> Vessel | None:
    return db.query(Vessel).filter(Vessel.vessel_id == vessel_id).first()

def get_vessel_by_imo(db: Session, imo_number: str) -> Vessel | None:
    """Kluczowa funkcja dla parsera LLM - szuka statku po niezmiennym numerze IMO."""
    return db.query(Vessel).filter(Vessel.imo_number == imo_number).first()


# ---------------------------------------------------------------------------
# Historia statku - dla wzbogacenia przez agenta "porównania z bazą"
# (FUN-003/FUN-011). Każda funkcja ma limit liczby wierszy - to jest
# pierwsza linia obrony przed przekroczeniem limitu 50kB JSON-a; druga
# linia (właściwe obcinanie, jeśli mimo limitów i tak jest za duży) jest
# w serwisie, który składa to w JSON.
# ---------------------------------------------------------------------------

def get_name_history(db: Session, vessel_id: uuid.UUID, limit: int = 10) -> list[VesselNameHistory]:
    return db.query(VesselNameHistory).filter(VesselNameHistory.vessel_id == vessel_id) \
        .order_by(VesselNameHistory.effective_from.desc()).limit(limit).all()


def get_technical_specs_history(db: Session, vessel_id: uuid.UUID, limit: int = 5) -> list[VesselTechnicalSpecs]:
    return db.query(VesselTechnicalSpecs).filter(VesselTechnicalSpecs.vessel_id == vessel_id) \
        .order_by(VesselTechnicalSpecs.effective_from.desc()).limit(limit).all()


def get_company_roles(db: Session, vessel_id: uuid.UUID, current_only: bool = True) -> list[VesselCompanyRole]:
    query = db.query(VesselCompanyRole).filter(VesselCompanyRole.vessel_id == vessel_id)
    if current_only:
        query = query.filter(VesselCompanyRole.is_current == True)
    return query.all()


def get_certificates(db: Session, vessel_id: uuid.UUID, limit: int = 20) -> list[VesselCertificate]:
    return db.query(VesselCertificate).filter(VesselCertificate.vessel_id == vessel_id) \
        .order_by(VesselCertificate.expiry_date.desc()).limit(limit).all()


def get_psc_inspections(db: Session, vessel_id: uuid.UUID, limit: int = 10) -> list[PSCInspection]:
    """Tylko najnowsze inspekcje - historia PSC bywa długa, a najstarsze
    wpisy mają najmniejszą wartość dla bieżącej decyzji."""
    return db.query(PSCInspection).filter(PSCInspection.vessel_id == vessel_id) \
        .order_by(PSCInspection.inspection_date.desc()).limit(limit).all()


def get_psc_deficiencies(db: Session, inspection_ids: list[uuid.UUID]) -> list[PSCDeficiency]:
    if not inspection_ids:
        return []
    return db.query(PSCDeficiency).filter(PSCDeficiency.inspection_id.in_(inspection_ids)).all()


def get_sanctions_screenings(db: Session, vessel_id: uuid.UUID, limit: int = 5) -> list[SanctionsScreening]:
    """Tylko najnowsze - to jest stan AKTUALNY zainteresowania, nie
    potrzeba całej historii przeglądów dla każdego starego wpisu."""
    return db.query(SanctionsScreening).filter(SanctionsScreening.vessel_id == vessel_id) \
        .order_by(SanctionsScreening.screened_at.desc()).limit(limit).all()


def get_current_risk_assessment(db: Session, vessel_id: uuid.UUID) -> VesselRiskAssessment | None:
    return db.query(VesselRiskAssessment).filter(
        VesselRiskAssessment.vessel_id == vessel_id,
        VesselRiskAssessment.is_current == True,
    ).first()


def get_previous_nominations(db: Session, vessel_id: uuid.UUID, exclude_nomination_id: uuid.UUID,
                              limit: int = 15) -> list[Nomination]:
    """Wcześniejsze nominacje TEGO SAMEGO statku - to jest 'historia
    poprzednich operacji w porcie' z notatki kolegi. Wyklucza bieżącą
    nominację (tę, dla której właśnie robimy wzbogacenie)."""
    return db.query(Nomination).filter(
        Nomination.vessel_id == vessel_id,
        Nomination.nomination_id != exclude_nomination_id,
    ).order_by(Nomination.created_at.desc()).limit(limit).all()


def get_cargo_for_nominations(db: Session, nomination_ids: list[uuid.UUID]) -> list[CargoManifest]:
    if not nomination_ids:
        return []
    return db.query(CargoManifest).filter(CargoManifest.nomination_id.in_(nomination_ids)).all()
import logging
from typing import Optional
import uuid

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import LLMParsingError, EntityNotFoundError
from app.models.operations import Nomination, NominationUnstructuredNote, CargoManifest, PortServiceOrder
from app.models.vessel import VesselTechnicalSpecs
from app.models.enums import NominationStatus, ImdgHazardClass, PortServiceType
from app.repositories import vessel_repository, port_repository, company_repository, country_repository

logger = logging.getLogger(__name__)


def _build_agent_payload(nomination: Nomination) -> dict:
    """
    Buduje payload wysyłany do agenta - wyłącznie dane, które realnie
    mamy z samego maila (treść + metadane), bez żadnego zgadywania.
    """
    return {
        "nomination_id": str(nomination.nomination_id),
        "email": {
            "subject": nomination.source_email_subject,
            "body": nomination.source_email_body_raw,
            "sender_address": nomination.source_email_sender_address,
            "received_at": nomination.source_email_received_at.isoformat()
                if nomination.source_email_received_at else None,
        },
    }


def call_extraction_agent(payload: dict) -> dict:
    """
    Wywołuje API agenta (wrapper kolegi na ElevenLabs) synchronicznie.
    Zwraca surowy JSON - walidacja/parsowanie do AgentExtractionResponse
    dzieje się wyżej, żeby błędy walidacji były jednoznacznie odróżnialne
    od błędów samego połączenia.
    """
    if not settings.AGENT_API_URL:
        raise LLMParsingError(details="Brak skonfigurowanego AGENT_API_URL - agent kolegi nie jest podłączony.")

    headers = {"Content-Type": "application/json"}
    if settings.AGENT_API_KEY:
        headers["Authorization"] = f"Bearer {settings.AGENT_API_KEY}"

    try:
        response = httpx.post(
            settings.AGENT_API_URL,
            json=payload,
            headers=headers,
            timeout=60.0,  # agenci głosowi/LLM-owi mogą odpowiadać wolniej niż zwykłe API
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise LLMParsingError(details=f"Błąd komunikacji z agentem ekstrakcji: {exc}")
    except ValueError as exc:  # response.json() zwrócił coś, co nie jest JSON-em
        raise LLMParsingError(details=f"Agent zwrócił niepoprawny JSON: {exc}")


def _resolve_imdg_class(raw_value: Optional[str]) -> ImdgHazardClass:
    """Mapuje string od agenta na enum bazy; nieznana/brakująca wartość -> 'none',
    żeby nigdy nie wywalić zapisu przez nieznaną wartość enuma."""
    if not raw_value:
        return ImdgHazardClass.none
    try:
        return ImdgHazardClass(raw_value)
    except ValueError:
        logger.warning("Agent zwrócił nieznaną klasę IMDG '%s', zapisuję jako 'none'.", raw_value)
        return ImdgHazardClass.none


def _resolve_service_type(raw_value: str) -> Optional[PortServiceType]:
    """Mapuje string od agenta na enum PortServiceType; nieznana wartość
    zwraca None (wiersz jest wtedy pomijany), żeby nigdy nie wywalić
    całego zapisu przez jedną nierozpoznaną usługę."""
    try:
        return PortServiceType(raw_value)
    except ValueError:
        logger.warning("Agent zwrócił nieznany typ usługi portowej '%s', pomijam.", raw_value)
        return None


def apply_extraction_result(db: Session, nomination: Nomination, extracted: dict) -> Nomination:
    """
    Mapuje wynik agenta na rekordy bazy:
      - vessel_id dociągany po IMO (jeśli agent znalazł IMO i statek już
        istnieje w bazie - to jest właśnie 'dociąganie brakujących danych
        z istniejących rekordów')
      - wymiary/tonaż statku (LOA, draft, DWT, TEU...) -> nowy wiersz w
        vessel_technical_specs (wersjonowane, data_source='email_nomination')
      - destination_port_id po UN/LOCODE
      - nominating_company_id po nazwie firmy (fuzzy match)
      - requested_berth_id po nazwie nabrzeża (jeśli armator o nie poprosił)
      - cargo -> nowy wiersz w cargo_manifests
      - usługi portowe (holownik, pilotaż, zmiana załogi...) -> nowe
        wiersze w port_service_orders, powiązane z nomination_id (bo
        port_call jeszcze nie istnieje na tym etapie)
      - notatki nieustrukturyzowane -> nomination_unstructured_notes,
        oznaczone requires_human_review=True (zawsze wymagają przeglądu
        człowieka, bo to dane "nie zmieściły się" w sztywne kolumny)

    Nic nie nadpisuje na ślepo: jeśli agent nie znalazł jakiegoś pola
    (None), istniejąca wartość w nominacji NIE jest czyszczona.
    """
    vessel = extracted.get("vessel") or {}
    cargo = extracted.get("cargo") or {}
    contact = extracted.get("nominating_contact") or {}
    technical_specs = vessel.get("technical_specs") or {}

    # --- Statek: dociągamy po IMO, jeśli agent go znalazł ---
    if vessel.get("imo_number"):
        found_vessel = vessel_repository.get_vessel_by_imo(db, vessel["imo_number"])
        if found_vessel:
            nomination.vessel_id = found_vessel.vessel_id
        else:
            logger.warning(
                "Agent zwrócił IMO %s, ale statku nie ma w bazie - nomination_id=%s wymaga ręcznej weryfikacji.",
                vessel["imo_number"], nomination.nomination_id,
            )

    # --- Port docelowy: dociągamy po UN/LOCODE ---
    if extracted.get("port_locode"):
        found_port = port_repository.get_port_by_name_or_locode(db, extracted["port_locode"])
        if found_port:
            nomination.destination_port_id = found_port.port_id

    # --- Firma nominująca: dociągamy po nazwie (fuzzy) ---
    if extracted.get("nominating_company_name"):
        found_company = company_repository.get_company_by_name(db, extracted["nominating_company_name"])
        if found_company:
            nomination.nominating_company_id = found_company.company_id

    # --- Osoba kontaktowa: dociągamy po e-mailu, potem po imieniu+nazwisku ---
    if nomination.nominating_company_id:
        found_contact = None
        if contact.get("email"):
            found_contact = company_repository.get_contact_by_email(db, contact["email"])
        if not found_contact and contact.get("first_name") and contact.get("last_name"):
            found_contact = company_repository.get_contact_by_name(
                db, nomination.nominating_company_id, contact["first_name"], contact["last_name"]
            )
        if found_contact:
            nomination.nominating_contact_id = found_contact.contact_id

    # --- Nabrzeże, o które poprosił armator (NIE to przydzielone systemowo) ---
    if extracted.get("requested_berth_name") and nomination.destination_port_id:
        found_berth = port_repository.get_berth_by_name(
            db, nomination.destination_port_id, extracted["requested_berth_name"]
        )
        if found_berth:
            nomination.requested_berth_id = found_berth.berth_id

    # --- Daty ---
    if extracted.get("eta"):
        nomination.eta = extracted["eta"]
    if extracted.get("etd"):
        nomination.etd = extracted["etd"]

    # --- Metadane ekstrakcji - zawsze zapisujemy, niezależnie od tego, co
    # udało się dociągnąć, żeby zachować pełny audyt tego, co agent zwrócił ---
    nomination.llm_extraction_metadata = {
        "model": extracted.get("extraction_model"),
        "confidence": extracted.get("confidence_score"),
        "fields_missing": extracted.get("fields_missing", []),
        "raw_response": extracted,
    }
    nomination.status = NominationStatus.parsed_pending_review

    db.add(nomination)

    # --- Ładunek: jeśli agent znalazł cokolwiek o ładunku, zapisujemy nowy wiersz ---
    if cargo.get("description"):
        origin_country = country_repository.get_country_by_iso_alpha2(db, cargo.get("origin_country"))
        destination_country = country_repository.get_country_by_iso_alpha2(db, cargo.get("destination_country"))

        cargo_manifest = CargoManifest(
            nomination_id=nomination.nomination_id,
            cargo_description=cargo["description"],
            cargo_quantity=cargo.get("quantity"),
            cargo_unit=cargo.get("unit"),
            imdg_hazard_class=_resolve_imdg_class(cargo.get("imdg_hazard_class")),
            un_number=cargo.get("un_number"),
            requires_refrigeration=bool(cargo.get("requires_refrigeration")),
            target_temperature_celsius=cargo.get("target_temperature_celsius"),
            is_perishable=bool(cargo.get("is_perishable")),
            origin_country_id=origin_country.country_id if origin_country else None,
            destination_country_id=destination_country.country_id if destination_country else None,
        )
        db.add(cargo_manifest)

    # --- Wymiary/tonaż statku (LOA, draft, DWT, TEU...) - zapisujemy
    # tylko jeśli agent znalazł CHOĆ JEDNĄ wartość i mamy już znany
    # vessel_id (kolumna NOT NULL w bazie, więc bez statku nie ma gdzie
    # tego podczepić - trafi wtedy do unstructured_notes niżej) ---
    if nomination.vessel_id and any(v is not None for v in technical_specs.values()):
        db.add(VesselTechnicalSpecs(
            vessel_id=nomination.vessel_id,
            length_overall_meters=technical_specs.get("length_overall_meters"),
            beam_meters=technical_specs.get("beam_meters"),
            draft_meters=technical_specs.get("draft_meters"),
            air_draft_meters=technical_specs.get("air_draft_meters"),
            gross_tonnage=technical_specs.get("gross_tonnage"),
            net_tonnage=technical_specs.get("net_tonnage"),
            deadweight_tonnage=technical_specs.get("deadweight_tonnage"),
            max_speed_knots=technical_specs.get("max_speed_knots"),
            has_ice_class=bool(technical_specs.get("has_ice_class")),
            ice_class_designation=technical_specs.get("ice_class_designation"),
            container_capacity_teu=technical_specs.get("container_capacity_teu"),
            has_reefer_plugs=bool(technical_specs.get("has_reefer_plugs")),
            reefer_plug_count=technical_specs.get("reefer_plug_count"),
            data_source="email_nomination",
        ))

    # --- Usługi portowe, o które armator poprosił w mailu (holownik,
    # pilotaż, zmiana załogi...) - powiązane z nomination_id, bo
    # port_call jeszcze nie istnieje na tym etapie ---
    for service_request in extracted.get("requested_services", []):
        resolved_type = _resolve_service_type(service_request.get("service_type"))
        if resolved_type is None:
            continue
        db.add(PortServiceOrder(
            nomination_id=nomination.nomination_id,
            service_type=resolved_type,
            notes=service_request.get("notes"),
            scheduled_for=service_request.get("scheduled_for"),
        ))

    # --- Notatki nieustrukturyzowane - zawsze wymagają przeglądu człowieka ---
    for note_text in extracted.get("unstructured_notes", []):
        db.add(NominationUnstructuredNote(
            nomination_id=nomination.nomination_id,
            note_text=note_text,
            extracted_by="agent_elevenlabs",
            confidence_score=extracted.get("confidence_score"),
            requires_human_review=True,
        ))

    db.commit()
    db.refresh(nomination)
    return nomination


def extract_and_apply(db: Session, nomination_id: uuid.UUID) -> Nomination:
    """
    Pełny przepływ dla jednej nominacji: wywołuje agenta z treścią maila,
    a wynik mapuje na rekordy bazy.
    """
    nomination = db.query(Nomination).filter(Nomination.nomination_id == nomination_id).first()
    if not nomination:
        raise EntityNotFoundError(entity_name="Nomination", entity_id=nomination_id)

    payload = _build_agent_payload(nomination)
    extracted = call_extraction_agent(payload)
    return apply_extraction_result(db, nomination, extracted)
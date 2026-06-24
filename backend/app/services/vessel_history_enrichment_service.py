import json
import logging
import threading
import time
import uuid as uuid_module
from typing import Optional

from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import LLMParsingError, EntityNotFoundError
from app.models.operations import Nomination
from app.repositories import vessel_repository, port_repository, country_repository
from app.schemas.vessel_enrichment import (
    VesselHistoryPayload, VesselIdentitySnapshot, NameHistoryEntry, TechnicalSpecsSnapshot,
    CompanyRoleEntry, CertificateEntry, PSCInspectionEntry, PSCDeficiencySummary,
    SanctionsScreeningEntry, PreviousNominationEntry, PreviousCargoSummary, VesselEnrichmentResponse,
)

logger = logging.getLogger(__name__)

# Limit z notatki kolegi (FUN-003/FUN-011): JSON wysyłany do agenta
# wzbogacenia nie może przekroczyć 50 kB.
MAX_PAYLOAD_SIZE_BYTES = 50 * 1024

AGENT_RESPONSE_TIMEOUT_SECONDS = 60.0

# Ile czekamy, aż WebSocket faktycznie się połączy po start_session()
# (start_session() startuje wątek w tle i wraca natychmiast - nie czeka
# na połączenie - więc send_user_message() wywołane zaraz po niej może
# trafić na "Session not started or websocket not connected").
WEBSOCKET_READY_TIMEOUT_SECONDS = 10.0
WEBSOCKET_READY_POLL_INTERVAL_SECONDS = 0.1


def _wait_for_websocket_ready(conversation: Conversation) -> None:
    """Czeka, aż wątek startujący sesję faktycznie połączy WebSocket -
    patrz identyczna funkcja i wyjaśnienie w agent_extraction_service.py."""
    deadline = time.monotonic() + WEBSOCKET_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if getattr(conversation, "_ws", None):
            return
        time.sleep(WEBSOCKET_READY_POLL_INTERVAL_SECONDS)
    raise LLMParsingError(
        details=f"Połączenie WebSocket z agentem wzbogacenia nie zostało ustanowione w ciągu "
                f"{WEBSOCKET_READY_TIMEOUT_SECONDS}s."
    )


def _payload_size_bytes(payload: VesselHistoryPayload) -> int:
    return len(payload.model_dump_json().encode("utf-8"))


def build_vessel_history_payload(db: Session, nomination: Nomination) -> VesselHistoryPayload:
    """
    Składa JSON z PEŁNĄ historią statku z bazy (FUN-003/FUN-011) -
    identyfikacja, historia nazw/flag, specy techniczne, role firm,
    certyfikaty, inspekcje PSC, sankcje, ocena ryzyka, poprzednie
    nominacje + ich ładunek.

    Jeśli mimo limitów liczby wierszy w repozytorium wynik i tak
    przekracza MAX_PAYLOAD_SIZE_BYTES (statek z bardzo długą historią),
    progresywnie obcinamy NAJMNIEJ krytyczne sekcje w ustalonej
    kolejności - każde obcięcie jest jawnie zapisane w
    `truncated_sections`, żeby agent wiedział, że dostał niepełny obraz,
    a nie cichą, niewidoczną stratę danych.
    """
    if not nomination.vessel_id:
        raise LLMParsingError(details="Nominacja nie ma jeszcze przypisanego statku - nie można zbudować historii.")

    vessel = vessel_repository.get_vessel_by_id(db, nomination.vessel_id)
    if not vessel:
        raise EntityNotFoundError(entity_name="Vessel", entity_id=nomination.vessel_id)

    # --- Identyfikacja ---
    vessel_snapshot = VesselIdentitySnapshot(
        imo_number=vessel.imo_number,
        current_name=vessel.current_vessel_name,
        mmsi=vessel.mmsi,
        call_sign=vessel.call_sign,
        year_built=vessel.year_built,
        is_active=vessel.is_active,
    )

    # --- Historia nazw/flag ---
    name_history = []
    for entry in vessel_repository.get_name_history(db, vessel.vessel_id):
        country = country_repository.get_country_by_id(db, entry.flag_country_id)
        name_history.append(NameHistoryEntry(
            vessel_name=entry.vessel_name,
            flag_country_iso=country.iso_alpha2 if country else None,
            effective_from=entry.effective_from,
            effective_until=entry.effective_until,
        ))

    # --- Specy techniczne (historia wersji) ---
    technical_specs_history = [
        TechnicalSpecsSnapshot(
            length_overall_meters=spec.length_overall_meters,
            draft_meters=spec.draft_meters,
            deadweight_tonnage=spec.deadweight_tonnage,
            container_capacity_teu=spec.container_capacity_teu,
            has_ice_class=spec.has_ice_class,
            effective_from=spec.effective_from,
            data_source=spec.data_source,
        )
        for spec in vessel_repository.get_technical_specs_history(db, vessel.vessel_id)
    ]

    # --- Role firm (kto jest armatorem/operatorem/managerem) ---
    company_roles = []
    for role in vessel_repository.get_company_roles(db, vessel.vessel_id):
        from app.repositories import company_repository
        company = company_repository.get_company_by_id(db, role.company_id)
        if company:
            company_roles.append(CompanyRoleEntry(
                company_name=company.company_name,
                role_type=role.role_type.value if hasattr(role.role_type, "value") else role.role_type,
                is_current=role.is_current,
            ))

    # --- Certyfikaty ---
    from datetime import date
    today = date.today()
    certificates = [
        CertificateEntry(
            certificate_type=cert.certificate_type,
            expiry_date=cert.expiry_date,
            is_expired=(cert.expiry_date < today) if cert.expiry_date else None,
        )
        for cert in vessel_repository.get_certificates(db, vessel.vessel_id)
    ]

    # --- Inspekcje PSC + ich usterki ---
    inspections = vessel_repository.get_psc_inspections(db, vessel.vessel_id)
    inspection_ids = [i.inspection_id for i in inspections]
    all_deficiencies = vessel_repository.get_psc_deficiencies(db, inspection_ids)
    deficiencies_by_inspection: dict = {}
    for d in all_deficiencies:
        deficiencies_by_inspection.setdefault(d.inspection_id, []).append(d)

    psc_inspections = [
        PSCInspectionEntry(
            inspection_date=insp.inspection_date,
            inspecting_authority=insp.inspecting_authority,
            deficiency_count=insp.deficiency_count,
            was_detained=insp.was_detained,
            deficiencies=[
                PSCDeficiencySummary(severity=d.severity, description=d.deficiency_description)
                for d in deficiencies_by_inspection.get(insp.inspection_id, [])
            ],
        )
        for insp in inspections
    ]

    # --- Sankcje ---
    sanctions_screenings = [
        SanctionsScreeningEntry(
            list_source=s.list_source.value if hasattr(s.list_source, "value") else s.list_source,
            screening_result=s.screening_result.value if hasattr(s.screening_result, "value") else s.screening_result,
            screened_at=s.screened_at,
        )
        for s in vessel_repository.get_sanctions_screenings(db, vessel.vessel_id)
    ]

    # --- Ocena ryzyka ---
    risk_assessment = vessel_repository.get_current_risk_assessment(db, vessel.vessel_id)

    # --- Poprzednie nominacje + ich cargo ---
    previous_noms = vessel_repository.get_previous_nominations(db, vessel.vessel_id, nomination.nomination_id)
    previous_nom_ids = [n.nomination_id for n in previous_noms]
    all_cargo = vessel_repository.get_cargo_for_nominations(db, previous_nom_ids)
    cargo_by_nomination: dict = {}
    for c in all_cargo:
        cargo_by_nomination.setdefault(c.nomination_id, []).append(c)

    previous_nominations = []
    for nom in previous_noms:
        port = port_repository.get_port_by_id(db, nom.destination_port_id) if nom.destination_port_id else None
        previous_nominations.append(PreviousNominationEntry(
            nomination_id=str(nom.nomination_id),
            status=nom.status.value if hasattr(nom.status, "value") else nom.status,
            eta=nom.eta,
            port_name=port.port_name if port else None,
            cargo=[
                PreviousCargoSummary(
                    description=c.cargo_description,
                    imdg_hazard_class=c.imdg_hazard_class.value if hasattr(c.imdg_hazard_class, "value") else str(c.imdg_hazard_class),
                    requires_refrigeration=bool(c.requires_refrigeration),
                )
                for c in cargo_by_nomination.get(nom.nomination_id, [])
            ],
        ))

    payload = VesselHistoryPayload(
        nomination_id=str(nomination.nomination_id),
        vessel=vessel_snapshot,
        name_history=name_history,
        technical_specs_history=technical_specs_history,
        company_roles=company_roles,
        certificates=certificates,
        psc_inspections=psc_inspections,
        sanctions_screenings=sanctions_screenings,
        current_risk_score=float(risk_assessment.overall_risk_score) if risk_assessment else None,
        current_risk_tier=(risk_assessment.risk_tier.value if risk_assessment and hasattr(risk_assessment.risk_tier, "value")
                           else (risk_assessment.risk_tier if risk_assessment else None)),
        previous_nominations=previous_nominations,
    )

    return _enforce_size_limit(payload)


# Kolejność obcinania - od najmniej do najbardziej krytycznego dla
# bieżącej decyzji. Usterki PSC (deficiencies) to zazwyczaj najbardziej
# "rozdmuchana" sekcja (tekstowe opisy), więc idą pierwsze.
def _enforce_size_limit(payload: VesselHistoryPayload) -> VesselHistoryPayload:
    if _payload_size_bytes(payload) <= MAX_PAYLOAD_SIZE_BYTES:
        return payload

    truncation_steps = [
        ("psc_deficiencies_details", lambda p: [
            PSCInspectionEntry(**{**i.model_dump(), "deficiencies": []}) for i in p.psc_inspections
        ]),
        ("previous_nominations_cargo_details", lambda p: [
            PreviousNominationEntry(**{**n.model_dump(), "cargo": []}) for n in p.previous_nominations
        ]),
        ("technical_specs_history", lambda p: p.technical_specs_history[:1]),  # tylko najnowsza wersja
        ("name_history", lambda p: p.name_history[:3]),
        ("previous_nominations", lambda p: p.previous_nominations[:5]),
        ("psc_inspections", lambda p: p.psc_inspections[:3]),
        ("certificates", lambda p: p.certificates[:5]),
    ]

    for section_name, reducer in truncation_steps:
        if section_name == "psc_deficiencies_details":
            payload.psc_inspections = reducer(payload)
        elif section_name == "previous_nominations_cargo_details":
            payload.previous_nominations = reducer(payload)
        elif section_name == "technical_specs_history":
            payload.technical_specs_history = reducer(payload)
        elif section_name == "name_history":
            payload.name_history = reducer(payload)
        elif section_name == "previous_nominations":
            payload.previous_nominations = reducer(payload)
        elif section_name == "psc_inspections":
            payload.psc_inspections = reducer(payload)
        elif section_name == "certificates":
            payload.certificates = reducer(payload)

        payload.truncated_sections.append(section_name)

        if _payload_size_bytes(payload) <= MAX_PAYLOAD_SIZE_BYTES:
            logger.info(
                "Payload historii statku %s obcięty do limitu %d bajtów po krokach: %s",
                payload.vessel.imo_number, MAX_PAYLOAD_SIZE_BYTES, payload.truncated_sections,
            )
            return payload

    # Ostatnia linia obrony - nawet po wszystkich obcięciach za duże
    # (statek z absurdalnie długą historią certyfikatów/ról firm).
    logger.warning(
        "Payload historii statku %s przekracza limit %d bajtów nawet po pełnym obcięciu (%d bajtów).",
        payload.vessel.imo_number, MAX_PAYLOAD_SIZE_BYTES, _payload_size_bytes(payload),
    )
    return payload


def call_enrichment_agent(payload: VesselHistoryPayload) -> dict:
    """
    Wywołuje DRUGIEGO, osobnego agenta ElevenLabs (inny agent_id niż ten
    do ekstrakcji maila) - ten agent dostaje całą historię statku i ma
    zaproponować konfigurację + wskazać niespójności/braki do dopytania
    armatora. Mechanika identyczna jak w agent_extraction_service.py
    (Chat Mode, callback + threading.Event), ale inny agent_id.
    """
    if not settings.ELEVENLABS_API_KEY or not settings.ELEVENLABS_ENRICHMENT_AGENT_ID:
        raise LLMParsingError(
            details="Brak ELEVENLABS_API_KEY lub ELEVENLABS_ENRICHMENT_AGENT_ID - "
                    "agent wzbogacenia historii statku nie jest skonfigurowany."
        )

    client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

    response_received = threading.Event()
    result: dict = {"text": None}

    def on_agent_response(response: str) -> None:
        result["text"] = response
        response_received.set()

    def on_agent_correction(original: str, corrected: str) -> None:
        result["text"] = corrected

    config = ConversationInitiationData(
        conversation_config_override={"conversation": {"text_only": True}},
        dynamic_variables={"nomination_id": payload.nomination_id},
    )

    conversation = Conversation(
        client,
        settings.ELEVENLABS_ENRICHMENT_AGENT_ID,
        requires_auth=True,
        config=config,
        callback_agent_response=on_agent_response,
        callback_agent_response_correction=on_agent_correction,
    )

    try:
        conversation.start_session()
        _wait_for_websocket_ready(conversation)
        conversation.send_user_message(payload.model_dump_json())

        if not response_received.wait(timeout=AGENT_RESPONSE_TIMEOUT_SECONDS):
            raise LLMParsingError(details=f"Agent wzbogacenia nie odpowiedział w ciągu {AGENT_RESPONSE_TIMEOUT_SECONDS}s.")
    finally:
        conversation.end_session()

    if not result["text"]:
        raise LLMParsingError(details="Agent wzbogacenia zwrócił pustą odpowiedź.")

    try:
        return json.loads(result["text"])
    except ValueError as exc:
        raise LLMParsingError(details=f"Agent wzbogacenia zwrócił niepoprawny JSON: {exc}. Treść: {result['text'][:500]}")


def enrich_nomination_with_vessel_history(db: Session, nomination_id: uuid_module.UUID) -> VesselEnrichmentResponse:
    """
    Pełny przepływ FUN-003/FUN-011: budujemy historię statku z bazy,
    wysyłamy do agenta wzbogacenia, zwracamy jego propozycję konfiguracji
    + listę niespójności do wyświetlenia agentowi portowemu w UI.

    Wynik NIE jest automatycznie zapisywany do nominacji - to tylko
    PROPOZYCJA (zgodnie z notatką: "guzik do approve, dane jako pola do
    modyfikacji") - zapis następuje przez istniejące PATCH/assign-berth
    po tym, jak agent portowy zatwierdzi/zmodyfikuje propozycję w UI.
    """
    nomination = db.query(Nomination).filter(Nomination.nomination_id == nomination_id).first()
    if not nomination:
        raise EntityNotFoundError(entity_name="Nomination", entity_id=nomination_id)

    payload = build_vessel_history_payload(db, nomination)
    raw_response = call_enrichment_agent(payload)
    return VesselEnrichmentResponse.model_validate(raw_response)
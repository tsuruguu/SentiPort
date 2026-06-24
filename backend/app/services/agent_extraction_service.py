import json
import logging
import threading
import time
from typing import List, Optional
import uuid

from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation, ConversationInitiationData
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.config import settings
from app.core.exceptions import LLMParsingError, EntityNotFoundError
from app.models.operations import Nomination, NominationUnstructuredNote, CargoManifest, PortServiceOrder, \
    NominationAttachment
from app.models.vessel import VesselTechnicalSpecs
from app.models.enums import NominationStatus, ImdgHazardClass, PortServiceType
from app.repositories import vessel_repository, port_repository, company_repository, country_repository

logger = logging.getLogger(__name__)

# Ile maksymalnie czekamy na odpowiedź agenta w jednej "rozmowie" o mailu
# nominacyjnym. Agenci konwersacyjni bywają wolniejsi niż zwykłe API.
AGENT_RESPONSE_TIMEOUT_SECONDS = 60.0

# Ile czekamy, aż WebSocket faktycznie się połączy po start_session()
# (start_session() startuje wątek w tle i wraca natychmiast - NIE czeka
# na połączenie - więc send_user_message() wywołane zaraz po niej może
# trafić na "Session not started or websocket not connected").
WEBSOCKET_READY_TIMEOUT_SECONDS = 10.0
WEBSOCKET_READY_POLL_INTERVAL_SECONDS = 0.1

# Ile czekamy, aż serwer ElevenLabs przyśle conversation_id po
# start_session() - potrzebny TYLKO gdy mamy załączniki do wysłania
# (upload_file wymaga już istniejącej, aktywnej konwersacji).
CONVERSATION_ID_TIMEOUT_SECONDS = 10.0
CONVERSATION_ID_POLL_INTERVAL_SECONDS = 0.1


def _strip_markdown_json_fence(text: str) -> str:
    """
    Agenci konwersacyjni czasem (mimo instrukcji w prompcie) owijają
    odpowiedź w markdown code fence, np.:
        ```json
        {...}
        ```
    json.loads() na takim tekście wybucha na pierwszym znaku
    ("Expecting value: line 1 column 1"), bo to nie zaczyna się od `{`.
    Zdejmujemy fence, jeśli jest - bezpieczne, bo czysty JSON (bez
    fence) przechodzi przez to bez zmian.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        # Usuń pierwszą linię (```json albo samo ```) i ewentualne
        # zamykające ``` na końcu.
        lines = stripped.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


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


def _wait_for_websocket_ready(conversation: Conversation) -> None:
    """
    Czeka, aż wątek startujący sesję faktycznie połączy WebSocket.

    UWAGA - kruchość: start_session() w SDK (elevenlabs==2.54.0) tylko
    odpala wątek w tle i wraca natychmiast - nie czeka na połączenie.
    Wywołanie send_user_message()/send_multimodal_message() zaraz po
    start_session() bywa więc race-condition: trafia na moment, w
    którym self._ws jest jeszcze None, i SDK rzuca RuntimeError
    ("Session not started or websocket not connected"). Czekamy więc na
    prywatny atrybut `_ws` z krótkim pollingiem - to ten sam wzorzec, co
    przy _wait_for_conversation_id. Jeśli po aktualizacji SDK to
    przestanie działać, szukać publicznej metody/callbacku potwierdzenia
    otwarcia połączenia w changelogu elevenlabs-python.
    """
    deadline = time.monotonic() + WEBSOCKET_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if getattr(conversation, "_ws", None):
            return
        time.sleep(WEBSOCKET_READY_POLL_INTERVAL_SECONDS)
    raise LLMParsingError(
        details=f"Połączenie WebSocket z agentem nie zostało ustanowione w ciągu "
                f"{WEBSOCKET_READY_TIMEOUT_SECONDS}s."
    )


def _wait_for_conversation_id(conversation: Conversation) -> str:
    """
    Czeka, aż SDK ustali ID aktywnej konwersacji (przychodzi z serwera
    krótko po start_session(), asynchronicznie).

    UWAGA - kruchość: SDK (elevenlabs==2.54.0) nie udostępnia tego ID
    publicznie przed końcem sesji (wait_for_session_end() blokuje do
    zamknięcia, czyli za późno na upload pliku W TRAKCIE rozmowy).
    Czytamy więc prywatny atrybut `_conversation_id` z krótkim pollingiem.
    Jeśli po aktualizacji SDK to przestanie działać, szukać publicznego
    odpowiednika (np. property `conversation_id` albo callback startowy)
    w changelogu elevenlabs-python.
    """
    deadline = time.monotonic() + CONVERSATION_ID_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        conv_id = getattr(conversation, "_conversation_id", None)
        if conv_id:
            return conv_id
        time.sleep(CONVERSATION_ID_POLL_INTERVAL_SECONDS)
    raise LLMParsingError(
        details=f"Nie udało się uzyskać conversation_id w ciągu {CONVERSATION_ID_TIMEOUT_SECONDS}s "
                f"- nie można wysłać załączników."
    )


def _upload_attachments(client: ElevenLabs, conversation_id: str, attachments: List[NominationAttachment]) -> List[str]:
    """
    Wgrywa załączniki PDF do aktywnej konwersacji przez REST endpoint
    (POST /v1/convai/conversations/:id/files), zwraca listę file_id do
    przekazania agentowi przez send_multimodal_message.

    Błąd przy jednym pliku nie przerywa wysyłki pozostałych - logujemy i
    kontynuujemy, żeby jeden zepsuty plik nie zablokował całej ekstrakcji.
    """
    file_ids = []
    for att in attachments:
        try:
            response = client.conversational_ai.conversations.files.create(
                conversation_id,
                file=(att.filename, att.file_data, att.content_type),
            )
            file_ids.append(response.file_id)
        except Exception:
            logger.exception("Nie udało się wgrać załącznika '%s' do konwersacji %s.", att.filename, conversation_id)
    return file_ids


def call_extraction_agent(payload: dict, attachments: Optional[List[NominationAttachment]] = None) -> dict:
    """
    Wywołuje agenta ElevenLabs (Chat Mode - czysty tekst, bez audio) i
    czeka na jego odpowiedź synchronicznie.

    Mechanika: ElevenLabs SDK jest zaprojektowany wokół żywej sesji
    konwersacyjnej z odpowiedziami dostarczanymi przez callback
    (`callback_agent_response`), nie jako zwrotka z funkcji. Żeby
    wpasować to w nasz model "wyślij request, dostań response",
    otwieramy sesję, wysyłamy treść maila (+ ewentualne załączniki PDF
    z maila armatora), i blokujemy się na threading.Event, aż callback
    dostarczy pierwszą odpowiedź agenta - lub aż upłynie timeout.

    Jeśli `attachments` nie jest pustą listą: po starcie sesji czekamy na
    conversation_id, wgrywamy każdy plik przez REST, i wysyłamy JEDNĄ
    wiadomość multimodalną (tekst maila + referencje do plików) - agent
    sam wyciągnie dane z PDF-a zgodnie ze swoim systemowym promptem.
    Bez załączników wysyłamy zwykłą wiadomość tekstową (szybsza ścieżka,
    nie wymaga czekania na conversation_id).

    Agent (zgodnie z jego systemowym promptem) ma odpowiedzieć czystym
    JSON-em zgodnym z naszym kontraktem (AgentExtractionResponse) - tutaj
    tylko parsujemy ten tekst jako JSON.
    """
    if not settings.ELEVENLABS_API_KEY or not settings.ELEVENLABS_AGENT_ID:
        raise LLMParsingError(
            details="Brak ELEVENLABS_API_KEY lub ELEVENLABS_AGENT_ID - agent kolegi nie jest skonfigurowany."
        )

    attachments = attachments or []
    client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

    response_received = threading.Event()
    result: dict = {"text": None, "error": None}

    def on_agent_response(response: str) -> None:
        # Pierwsza odpowiedź agenta to nasz wynik - zwalniamy blokadę.
        result["text"] = response
        response_received.set()

    def on_agent_correction(original: str, corrected: str) -> None:
        # Agent czasem poprawia własną wypowiedź - bierzemy finalną wersję,
        # jeśli zdąży przyjść przed timeoutem.
        result["text"] = corrected

    conversation_override = {"conversation": {"text_only": True}}
    config = ConversationInitiationData(
        conversation_config_override=conversation_override,
        dynamic_variables={"nomination_id": payload["nomination_id"]},
    )

    conversation = Conversation(
        client,
        settings.ELEVENLABS_AGENT_ID,
        requires_auth=True,
        config=config,
        callback_agent_response=on_agent_response,
        callback_agent_response_correction=on_agent_correction,
    )

    try:
        conversation.start_session()
        _wait_for_websocket_ready(conversation)
        email_message = json.dumps(payload["email"], ensure_ascii=False)

        if attachments:
            conversation_id = _wait_for_conversation_id(conversation)
            file_ids = _upload_attachments(client, conversation_id, attachments)
            if file_ids:
                # Jedna wiadomość multimodalna: tekst maila + referencje
                # do wgranych plików - agent czyta oba na raz.
                for file_id in file_ids[:-1]:
                    conversation.send_multimodal_message(file_id=file_id)
                conversation.send_multimodal_message(text=email_message, file_id=file_ids[-1])
            else:
                logger.warning("Brak poprawnie wgranych załączników - wysyłam tylko tekst maila.")
                conversation.send_user_message(email_message)
        else:
            conversation.send_user_message(email_message)

        if not response_received.wait(timeout=AGENT_RESPONSE_TIMEOUT_SECONDS):
            raise LLMParsingError(
                details=f"Agent nie odpowiedział w ciągu {AGENT_RESPONSE_TIMEOUT_SECONDS}s."
            )
    finally:
        conversation.end_session()

    if not result["text"]:
        raise LLMParsingError(details="Agent zwrócił pustą odpowiedź.")

    try:
        return json.loads(_strip_markdown_json_fence(result["text"]))
    except ValueError as exc:
        raise LLMParsingError(details=f"Agent zwrócił niepoprawny JSON: {exc}. Treść: {result['text'][:500]}")


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
      - cargo_items -> WIELE wierszy w cargo_manifests (statek może
        wieźć kilka różnych ładunków na raz, np. część suchych
        kontenerów + część reefer + część niebezpiecznych)
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
    cargo_items = extracted.get("cargo_items") or []
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

    # --- Ładunek: statek może wieźć kilka różnych ładunków na raz, więc
    # zapisujemy WSZYSTKIE elementy z listy jako osobne wiersze ---
    for cargo in cargo_items:
        if not cargo.get("description"):
            continue  # description jest NOT NULL w bazie - bez niego pomijamy element

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
    Pełny przepływ dla jednej nominacji: wywołuje agenta z treścią maila
    (+ ewentualne nieprzesłane jeszcze załączniki PDF), a wynik mapuje
    na rekordy bazy.

    Załączniki są wysyłane tylko raz - jeśli ten endpoint zostanie
    wywołany powtórnie dla tej samej nominacji (np. ręczna ponowna
    próba), pliki już oznaczone jako sent_to_agent_at nie są wysyłane
    drugi raz.
    """
    nomination = db.query(Nomination).filter(Nomination.nomination_id == nomination_id).first()
    if not nomination:
        raise EntityNotFoundError(entity_name="Nomination", entity_id=nomination_id)

    pending_attachments = db.query(NominationAttachment).filter(
        NominationAttachment.nomination_id == nomination_id,
        NominationAttachment.sent_to_agent_at.is_(None),
    ).all()

    payload = _build_agent_payload(nomination)
    extracted = call_extraction_agent(payload, attachments=pending_attachments)

    if pending_attachments:
        now = func.now()
        for att in pending_attachments:
            att.sent_to_agent_at = now
            db.add(att)

    return apply_extraction_result(db, nomination, extracted)
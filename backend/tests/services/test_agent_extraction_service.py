import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services import agent_extraction_service
from app.core.exceptions import LLMParsingError, EntityNotFoundError
from app.models.operations import Nomination


def _make_nomination(**overrides):
    nom = Nomination(
        nomination_id=uuid.uuid4(),
        vessel_id=uuid.uuid4(),
        nominating_company_id=uuid.uuid4(),
        destination_port_id=uuid.uuid4(),
        source_email_subject="Nominacja - MV Test",
        source_email_body_raw="Treść maila...",
        source_email_sender_address="armator1@armatorzy.pl",
        source_email_received_at=datetime(2026, 6, 23, 17, 30, tzinfo=timezone.utc),
    )
    for key, value in overrides.items():
        setattr(nom, key, value)
    return nom


def test_build_agent_payload_contains_only_real_email_fields():
    nomination = _make_nomination()
    payload = agent_extraction_service._build_agent_payload(nomination)

    assert payload["nomination_id"] == str(nomination.nomination_id)
    assert payload["email"]["subject"] == "Nominacja - MV Test"
    assert payload["email"]["sender_address"] == "armator1@armatorzy.pl"
    assert payload["email"]["received_at"] == "2026-06-23T17:30:00+00:00"


@patch("app.services.agent_extraction_service.Conversation")
@patch("app.services.agent_extraction_service.ElevenLabs")
@patch("app.services.agent_extraction_service.settings")
def test_call_extraction_agent_success(mock_settings, mock_elevenlabs_cls, mock_conversation_cls):
    """Symulujemy, że agent (przez callback_agent_response) odpowiada
    czystym JSON-em - powinniśmy go sparsować i zwrócić jako dict."""
    mock_settings.ELEVENLABS_API_KEY = "xi-secret-key"
    mock_settings.ELEVENLABS_AGENT_ID = "agent_test123"

    mock_conversation = MagicMock()
    mock_conversation_cls.return_value = mock_conversation

    def fake_start_session():
        # Symulujemy, że agent odpowiada natychmiast po starcie sesji,
        # zanim send_user_message zdąży się wykonać w "realnym" wątku -
        # wywołujemy callback ręcznie, tak jak zrobiłby to SDK w tle.
        callback = mock_conversation_cls.call_args.kwargs["callback_agent_response"]
        callback('{"vessel": {"imo_number": "9456789"}, "cargo": null}')

    mock_conversation.start_session.side_effect = fake_start_session

    result = agent_extraction_service.call_extraction_agent({
        "nomination_id": "abc",
        "email": {"subject": "test", "body": "test"},
    })

    assert result == {"vessel": {"imo_number": "9456789"}, "cargo": None}
    mock_conversation.send_user_message.assert_called_once()
    mock_conversation.end_session.assert_called_once()


@patch("app.services.agent_extraction_service.settings")
def test_call_extraction_agent_missing_credentials_raises(mock_settings):
    mock_settings.ELEVENLABS_API_KEY = None
    mock_settings.ELEVENLABS_AGENT_ID = None

    with pytest.raises(LLMParsingError):
        agent_extraction_service.call_extraction_agent({
            "nomination_id": "abc",
            "email": {"subject": "test", "body": "test"},
        })


@patch("app.services.agent_extraction_service.Conversation")
@patch("app.services.agent_extraction_service.ElevenLabs")
@patch("app.services.agent_extraction_service.settings")
def test_call_extraction_agent_timeout_raises(mock_settings, mock_elevenlabs_cls, mock_conversation_cls):
    """Jeśli agent nie odpowie w ogóle (callback nigdy nie woła set()),
    nie wisimy w nieskończoność - wybuchamy LLMParsingError po timeoucie."""
    mock_settings.ELEVENLABS_API_KEY = "xi-secret-key"
    mock_settings.ELEVENLABS_AGENT_ID = "agent_test123"
    mock_conversation_cls.return_value = MagicMock()  # start_session nic nie robi - brak odpowiedzi

    with patch("app.services.agent_extraction_service.AGENT_RESPONSE_TIMEOUT_SECONDS", 0.05):
        with pytest.raises(LLMParsingError):
            agent_extraction_service.call_extraction_agent({
                "nomination_id": "abc",
                "email": {"subject": "test", "body": "test"},
            })


@patch("app.services.agent_extraction_service.Conversation")
@patch("app.services.agent_extraction_service.ElevenLabs")
@patch("app.services.agent_extraction_service.settings")
def test_call_extraction_agent_invalid_json_raises(mock_settings, mock_elevenlabs_cls, mock_conversation_cls):
    """Jeśli agent odpowie tekstem, który nie jest poprawnym JSON-em
    (np. zwykłą rozmową), zgłaszamy jasny błąd zamiast cichego crasha."""
    mock_settings.ELEVENLABS_API_KEY = "xi-secret-key"
    mock_settings.ELEVENLABS_AGENT_ID = "agent_test123"

    mock_conversation = MagicMock()
    mock_conversation_cls.return_value = mock_conversation

    def fake_start_session():
        callback = mock_conversation_cls.call_args.kwargs["callback_agent_response"]
        callback("Przepraszam, nie rozumiem tej wiadomości.")

    mock_conversation.start_session.side_effect = fake_start_session

    with pytest.raises(LLMParsingError):
        agent_extraction_service.call_extraction_agent({
            "nomination_id": "abc",
            "email": {"subject": "test", "body": "test"},
        })


@patch("app.repositories.vessel_repository.get_vessel_by_imo")
@patch("app.repositories.port_repository.get_port_by_name_or_locode")
@patch("app.repositories.company_repository.get_company_by_name")
def test_apply_extraction_result_resolves_existing_records_by_lookup(
    mock_get_company, mock_get_port, mock_get_vessel
):
    """Kluczowy test: agent zwraca IMO/LOCODE/nazwę firmy, a serwis
    powinien DOCIĄGNĄĆ istniejące rekordy z bazy, nie tworzyć nowych ad-hoc."""
    mock_db = MagicMock()
    nomination = _make_nomination()

    existing_vessel = MagicMock(vessel_id=uuid.uuid4())
    existing_port = MagicMock(port_id=uuid.uuid4())
    existing_company = MagicMock(company_id=uuid.uuid4())
    mock_get_vessel.return_value = existing_vessel
    mock_get_port.return_value = existing_port
    mock_get_company.return_value = existing_company

    extracted = {
        "vessel": {"imo_number": "9456789", "name": "MV Test Vessel"},
        "port_locode": "PLGDY",
        "nominating_company_name": "Armator Sp. z o.o.",
        "eta": "2026-07-01T10:00:00Z",
        "confidence_score": 0.91,
        "extraction_model": "elevenlabs-agent-v1",
        "fields_missing": ["etd"],
        "cargo_items": [],
        "unstructured_notes": [],
    }

    result = agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    assert result.vessel_id == existing_vessel.vessel_id
    assert result.destination_port_id == existing_port.port_id
    assert result.nominating_company_id == existing_company.company_id
    assert result.eta == "2026-07-01T10:00:00Z"
    assert result.llm_extraction_metadata["confidence"] == 0.91
    assert result.llm_extraction_metadata["fields_missing"] == ["etd"]
    mock_db.commit.assert_called_once()


@patch("app.repositories.vessel_repository.get_vessel_by_imo")
def test_apply_extraction_result_does_not_clear_existing_value_when_agent_returns_nothing(mock_get_vessel):
    """Jeśli agent NIE znalazł numeru IMO w mailu, istniejący vessel_id
    (np. domyślny z importu) nie powinien zostać wyczyszczony."""
    mock_db = MagicMock()
    original_vessel_id = uuid.uuid4()
    nomination = _make_nomination(vessel_id=original_vessel_id)

    extracted = {
        "vessel": {"imo_number": None},
        "port_locode": None,
        "nominating_company_name": None,
        "cargo_items": [],
        "unstructured_notes": [],
    }

    result = agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    assert result.vessel_id == original_vessel_id
    mock_get_vessel.assert_not_called()


def test_apply_extraction_result_saves_single_cargo_manifest():
    mock_db = MagicMock()
    nomination = _make_nomination()

    extracted = {
        "vessel": {},
        "cargo_items": [
            {
                "description": "Kontenery mieszane, w tym reefer",
                "quantity": 120,
                "unit": "TEU",
                "imdg_hazard_class": "none",
                "requires_refrigeration": True,
                "is_perishable": True,
            },
        ],
        "unstructured_notes": ["Armator prosi o priorytetowe cumowanie"],
    }

    agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    # db.add powinien zostać wywołany dla: nomination + cargo_manifest + 1 notatka
    assert mock_db.add.call_count == 3


def test_apply_extraction_result_saves_multiple_cargo_manifests():
    """Statek może wieźć kilka różnych ładunków na raz (np. część
    kontenerów suchych + część reefer + część niebezpiecznych) - każdy
    element listy cargo_items powinien zapisać się jako osobny wiersz
    w cargo_manifests."""
    mock_db = MagicMock()
    nomination = _make_nomination()

    extracted = {
        "vessel": {},
        "cargo_items": [
            {
                "description": "Kontenery suche, towary ogólne",
                "quantity": 80,
                "unit": "TEU",
                "imdg_hazard_class": "none",
            },
            {
                "description": "Kontenery reefer, owoce mrożone",
                "quantity": 30,
                "unit": "TEU",
                "imdg_hazard_class": "none",
                "requires_refrigeration": True,
                "target_temperature_celsius": -18,
                "is_perishable": True,
            },
            {
                "description": "Materiały niebezpieczne klasa 3",
                "quantity": 10,
                "unit": "TEU",
                "imdg_hazard_class": "class_3_flammable_liquids",
                "un_number": "UN1203",
            },
        ],
        "unstructured_notes": [],
    }

    agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    added_objects = [call.args[0] for call in mock_db.add.call_args_list]
    cargo_manifests = [obj for obj in added_objects if obj.__class__.__name__ == "CargoManifest"]

    assert len(cargo_manifests) == 3
    descriptions = {cm.cargo_description for cm in cargo_manifests}
    assert descriptions == {
        "Kontenery suche, towary ogólne",
        "Kontenery reefer, owoce mrożone",
        "Materiały niebezpieczne klasa 3",
    }
    # Wszystkie powiązane z tą samą nominacją
    assert all(cm.nomination_id == nomination.nomination_id for cm in cargo_manifests)
    # Klasa IMDG poprawnie zmapowana per-element
    hazard_classes = {cm.cargo_description: cm.imdg_hazard_class for cm in cargo_manifests}
    from app.models.enums import ImdgHazardClass
    assert hazard_classes["Materiały niebezpieczne klasa 3"] == ImdgHazardClass.class_3_flammable_liquids
    assert hazard_classes["Kontenery suche, towary ogólne"] == ImdgHazardClass.none


def test_apply_extraction_result_skips_cargo_item_without_description():
    """description jest NOT NULL w bazie - element listy bez opisu jest
    pomijany, ale nie wywala całego zapisu."""
    mock_db = MagicMock()
    nomination = _make_nomination()

    extracted = {
        "vessel": {},
        "cargo_items": [
            {"description": "Kontenery suche", "quantity": 80},
            {"description": "", "quantity": 10},  # brak opisu - powinien być pominięty
            {"quantity": 5},  # brak description w ogóle
        ],
        "unstructured_notes": [],
    }

    agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    added_objects = [call.args[0] for call in mock_db.add.call_args_list]
    cargo_manifests = [obj for obj in added_objects if obj.__class__.__name__ == "CargoManifest"]
    assert len(cargo_manifests) == 1
    assert cargo_manifests[0].cargo_description == "Kontenery suche"


def test_apply_extraction_result_unknown_imdg_class_falls_back_to_none():
    """Jeśli agent zwróci wartość IMDG, której nie ma w naszym enumie,
    nie wybuchamy - zapisujemy 'none' i logujemy ostrzeżenie."""
    from app.models.enums import ImdgHazardClass
    resolved = agent_extraction_service._resolve_imdg_class("nieznana_klasa_xyz")
    assert resolved == ImdgHazardClass.none


def test_apply_extraction_result_saves_technical_specs_when_vessel_known():
    """Jeśli armator podał wymiary statku w mailu (LOA, draft, DWT, TEU)
    i mamy już znany vessel_id, zapisujemy nowy wiersz w
    vessel_technical_specs (potrzebne do doboru nabrzeża w Kroku 3)."""
    mock_db = MagicMock()
    nomination = _make_nomination()  # ma już vessel_id ustawiony

    extracted = {
        "vessel": {
            "technical_specs": {
                "length_overall_meters": 199.9,
                "draft_meters": 12.5,
                "deadweight_tonnage": 45000,
                "container_capacity_teu": 3500,
            }
        },
        "cargo_items": [],
        "unstructured_notes": [],
    }

    agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    # db.add: nomination + vessel_technical_specs = 2
    assert mock_db.add.call_count == 2
    added_objects = [call.args[0] for call in mock_db.add.call_args_list]
    specs = [obj for obj in added_objects if obj.__class__.__name__ == "VesselTechnicalSpecs"]
    assert len(specs) == 1
    assert specs[0].length_overall_meters == 199.9
    assert specs[0].deadweight_tonnage == 45000
    assert specs[0].data_source == "email_nomination"


def test_apply_extraction_result_skips_technical_specs_when_vessel_unknown():
    """Bez znanego vessel_id (FK NOT NULL w bazie) nie zapisujemy
    technical_specs - to by wywaliło insert."""
    mock_db = MagicMock()
    nomination = _make_nomination(vessel_id=None)

    extracted = {
        "vessel": {"technical_specs": {"length_overall_meters": 199.9}},
        "cargo_items": [],
        "unstructured_notes": [],
    }

    agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    added_objects = [call.args[0] for call in mock_db.add.call_args_list]
    specs = [obj for obj in added_objects if obj.__class__.__name__ == "VesselTechnicalSpecs"]
    assert len(specs) == 0


def test_apply_extraction_result_saves_requested_port_services():
    """Jeśli armator poprosił o usługi portowe w mailu (holownik,
    pilotaż...), zapisujemy je jako port_service_orders powiązane z
    nomination_id (port_call jeszcze nie istnieje na tym etapie)."""
    mock_db = MagicMock()
    nomination = _make_nomination()

    extracted = {
        "vessel": {},
        "cargo_items": [],
        "requested_services": [
            {"service_type": "towage", "notes": "2 holowniki przy wejściu"},
            {"service_type": "crew_change", "notes": "Zmiana 4 marynarzy"},
        ],
        "unstructured_notes": [],
    }

    agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    added_objects = [call.args[0] for call in mock_db.add.call_args_list]
    service_orders = [obj for obj in added_objects if obj.__class__.__name__ == "PortServiceOrder"]
    assert len(service_orders) == 2
    assert {so.notes for so in service_orders} == {"2 holowniki przy wejściu", "Zmiana 4 marynarzy"}
    assert all(so.nomination_id == nomination.nomination_id for so in service_orders)


def test_apply_extraction_result_skips_unknown_service_type():
    """Nieznany typ usługi (np. literówka od agenta) nie wywala zapisu -
    wiersz jest po prostu pomijany."""
    mock_db = MagicMock()
    nomination = _make_nomination()

    extracted = {
        "vessel": {},
        "cargo_items": [],
        "requested_services": [
            {"service_type": "nieznana_usluga_xyz", "notes": "coś dziwnego"},
        ],
        "unstructured_notes": [],
    }

    agent_extraction_service.apply_extraction_result(mock_db, nomination, extracted)

    added_objects = [call.args[0] for call in mock_db.add.call_args_list]
    service_orders = [obj for obj in added_objects if obj.__class__.__name__ == "PortServiceOrder"]
    assert len(service_orders) == 0


@patch("app.services.agent_extraction_service.call_extraction_agent")
def test_extract_and_apply_raises_when_nomination_missing(mock_call_agent):
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(EntityNotFoundError):
        agent_extraction_service.extract_and_apply(mock_db, uuid.uuid4())

    mock_call_agent.assert_not_called()


def _make_fake_attachment(filename="nominacja.pdf"):
    att = MagicMock()
    att.filename = filename
    att.content_type = "application/pdf"
    att.file_data = b"%PDF-1.4 fake content"
    att.sent_to_agent_at = None
    return att


@patch("app.services.agent_extraction_service.Conversation")
@patch("app.services.agent_extraction_service.ElevenLabs")
@patch("app.services.agent_extraction_service.settings")
def test_call_extraction_agent_uploads_attachment_and_sends_multimodal_message(
    mock_settings, mock_elevenlabs_cls, mock_conversation_cls
):
    """Jeśli są załączniki, agent powinien dostać wiadomość multimodalną
    (tekst + file_id), a nie zwykłą send_user_message."""
    mock_settings.ELEVENLABS_API_KEY = "xi-secret-key"
    mock_settings.ELEVENLABS_AGENT_ID = "agent_test123"

    mock_client = MagicMock()
    mock_elevenlabs_cls.return_value = mock_client
    mock_upload_response = MagicMock(file_id="file_abc123")
    mock_client.conversational_ai.conversations.files.create.return_value = mock_upload_response

    mock_conversation = MagicMock()
    # Symulujemy, że conversation_id jest już dostępny od razu po starcie.
    mock_conversation._conversation_id = "conv_xyz789"
    mock_conversation_cls.return_value = mock_conversation

    def fake_start_session():
        callback = mock_conversation_cls.call_args.kwargs["callback_agent_response"]
        callback('{"vessel": {"imo_number": "9456789"}}')

    mock_conversation.start_session.side_effect = fake_start_session

    att = _make_fake_attachment()
    result = agent_extraction_service.call_extraction_agent(
        {"nomination_id": "abc", "email": {"subject": "test", "body": "test"}},
        attachments=[att],
    )

    assert result == {"vessel": {"imo_number": "9456789"}}
    mock_client.conversational_ai.conversations.files.create.assert_called_once_with(
        "conv_xyz789",
        file=("nominacja.pdf", b"%PDF-1.4 fake content", "application/pdf"),
    )
    mock_conversation.send_multimodal_message.assert_called_once_with(
        text='{"subject": "test", "body": "test"}', file_id="file_abc123"
    )
    mock_conversation.send_user_message.assert_not_called()


@patch("app.services.agent_extraction_service.Conversation")
@patch("app.services.agent_extraction_service.ElevenLabs")
@patch("app.services.agent_extraction_service.settings")
def test_call_extraction_agent_falls_back_to_text_when_upload_fails(
    mock_settings, mock_elevenlabs_cls, mock_conversation_cls
):
    """Jeśli wgranie WSZYSTKICH załączników się nie powiedzie, agent i
    tak dostaje przynajmniej tekst maila - nie wybuchamy całkowicie."""
    mock_settings.ELEVENLABS_API_KEY = "xi-secret-key"
    mock_settings.ELEVENLABS_AGENT_ID = "agent_test123"

    mock_client = MagicMock()
    mock_elevenlabs_cls.return_value = mock_client
    mock_client.conversational_ai.conversations.files.create.side_effect = Exception("upload failed")

    mock_conversation = MagicMock()
    mock_conversation._conversation_id = "conv_xyz789"
    mock_conversation_cls.return_value = mock_conversation

    def fake_start_session():
        callback = mock_conversation_cls.call_args.kwargs["callback_agent_response"]
        callback('{"vessel": {}}')

    mock_conversation.start_session.side_effect = fake_start_session

    att = _make_fake_attachment()
    result = agent_extraction_service.call_extraction_agent(
        {"nomination_id": "abc", "email": {"subject": "test", "body": "test"}},
        attachments=[att],
    )

    assert result == {"vessel": {}}
    mock_conversation.send_user_message.assert_called_once()
    mock_conversation.send_multimodal_message.assert_not_called()


@patch("app.services.agent_extraction_service.Conversation")
@patch("app.services.agent_extraction_service.ElevenLabs")
@patch("app.services.agent_extraction_service.settings")
def test_call_extraction_agent_without_attachments_uses_plain_text_message(
    mock_settings, mock_elevenlabs_cls, mock_conversation_cls
):
    """Bez załączników nie czekamy na conversation_id - szybsza ścieżka
    przez zwykłą send_user_message."""
    mock_settings.ELEVENLABS_API_KEY = "xi-secret-key"
    mock_settings.ELEVENLABS_AGENT_ID = "agent_test123"

    mock_conversation = MagicMock()
    mock_conversation_cls.return_value = mock_conversation

    def fake_start_session():
        callback = mock_conversation_cls.call_args.kwargs["callback_agent_response"]
        callback('{"vessel": {}}')

    mock_conversation.start_session.side_effect = fake_start_session

    agent_extraction_service.call_extraction_agent(
        {"nomination_id": "abc", "email": {"subject": "test", "body": "test"}}
    )

    mock_conversation.send_user_message.assert_called_once()
    mock_conversation.send_multimodal_message.assert_not_called()


@patch("app.services.agent_extraction_service.apply_extraction_result")
@patch("app.services.agent_extraction_service.call_extraction_agent")
def test_extract_and_apply_passes_pending_attachments_and_marks_them_sent(mock_call_agent, mock_apply):
    """extract_and_apply powinien dociągnąć tylko NIEWYSŁANE jeszcze
    załączniki, przekazać je do agenta, i oznaczyć jako wysłane po
    udanym wywołaniu."""
    mock_db = MagicMock()
    nomination = _make_nomination()
    pending_attachment = _make_fake_attachment()

    # Pierwsze query().filter().first() -> nominacja; drugie query().filter().all() -> załączniki
    mock_db.query.return_value.filter.return_value.first.return_value = nomination
    mock_db.query.return_value.filter.return_value.all.return_value = [pending_attachment]

    mock_call_agent.return_value = {"vessel": {}}
    mock_apply.return_value = nomination

    agent_extraction_service.extract_and_apply(mock_db, nomination.nomination_id)

    mock_call_agent.assert_called_once()
    call_kwargs = mock_call_agent.call_args.kwargs
    assert call_kwargs["attachments"] == [pending_attachment]
    # Załącznik powinien zostać oznaczony jako wysłany
    assert pending_attachment.sent_to_agent_at is not None
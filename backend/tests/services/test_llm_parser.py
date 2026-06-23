import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_parser_service import parse_nomination_email_with_llm
from app.core.exceptions import LLMParsingError


@patch("app.services.llm_parser_service.settings")
@patch("app.services.llm_parser_service._get_client")
def test_parse_nomination_email_success(mock_get_client, mock_settings):
    mock_settings.OPENAI_API_KEY = "sk-test-key"  # wymuszamy ścieżkę "prawdziwego" wywołania, nie fallback-mocka
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    # Symulujemy idealną odpowiedź od modelu GPT
    mock_client.chat.completions.create.return_value.choices[0].message.content = '''
    {
        "vessel_imo": "9456789",
        "vessel_name": "Test Vessel",
        "port_name": "Gdynia",
        "eta": "2024-07-01T10:00:00Z",
        "cargo_description": "Frozen fish",
        "requires_reefer": true,
        "dangerous_goods": false
    }
    '''

    result = parse_nomination_email_with_llm("Subject", "Body content")

    assert result["vessel_name"] == "Test Vessel"
    assert result["requires_reefer"] is True
    assert "confidence_score" in result


@patch("app.services.llm_parser_service.settings")
@patch("app.services.llm_parser_service._get_client")
def test_parse_nomination_email_openai_failure(mock_get_client, mock_settings):
    mock_settings.OPENAI_API_KEY = "sk-test-key"
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    # Symulujemy wywrotkę API OpenAI (np. brak środków lub timeout)
    mock_client.chat.completions.create.side_effect = Exception("OpenAI API is down")

    with pytest.raises(LLMParsingError) as exc_info:
        parse_nomination_email_with_llm("Subject", "Body")

    assert "Błąd integracji z OpenAI" in str(exc_info.value.payload)


def test_parse_nomination_email_falls_back_to_mock_without_api_key():
    """Skoro projekt rezygnuje z OpenAI (agent głosowy realizowany przez
    ElevenLabs), kluczowe jest to, że brak OPENAI_API_KEY nie wywala
    aplikacji - funkcja po prostu zwraca dane mockowe."""
    with patch("app.services.llm_parser_service.settings") as mock_settings:
        mock_settings.OPENAI_API_KEY = None
        result = parse_nomination_email_with_llm("Subject", "Body")

    assert result["vessel_imo"] == "9456789"
    assert "confidence_score" in result
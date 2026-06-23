import pytest
from unittest.mock import patch
from app.services.llm_parser_service import parse_nomination_email_with_llm
from app.core.exceptions import LLMParsingError


@patch("app.services.llm_parser_service.client.chat.completions.create")
def test_parse_nomination_email_success(mock_openai_create):
    # Symulujemy idealną odpowiedź od modelu GPT
    mock_openai_create.return_value.choices[0].message.content = '''
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


@patch("app.services.llm_parser_service.client.chat.completions.create")
def test_parse_nomination_email_openai_failure(mock_openai_create):
    # Symulujemy wywrotkę API OpenAI (np. brak środków lub timeout)
    mock_openai_create.side_effect = Exception("OpenAI API is down")

    with pytest.raises(LLMParsingError) as exc_info:
        parse_nomination_email_with_llm("Subject", "Body")

    assert "Błąd integracji z OpenAI" in str(exc_info.value.payload)
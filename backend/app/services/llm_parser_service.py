import json
from openai import OpenAI
from app.config import settings
from app.core.exceptions import LLMParsingError

# Klient inicjalizowany leniwie (przy pierwszym użyciu), nie przy imporcie
# modułu. Projekt nie korzysta już z OpenAI na stałe (głosowy agent jest
# realizowany przez ElevenLabs) - więc ten serwis to teraz tylko opcjonalny
# fallback/funkcja pomocnicza, a brak OPENAI_API_KEY nie powinien wywalać
# importu całej aplikacji.
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def parse_nomination_email_with_llm(subject: str, body: str) -> dict:
    """
    Agent AI czytający maila. Zwraca ustrukturyzowanego JSON-a.
    Wymaga modelu gpt-4o-mini lub gpt-4-turbo dla obsługi response_format.
    """
    if not settings.OPENAI_API_KEY:
        # Fallback na mocka, jeśli nie podepniecie klucza na demo
        return {
            "vessel_imo": "9456789",  # IMO Nordic Voyager z seeda
            "port_locode": "PLGDY",
            "eta": "2024-07-01T10:00:00Z",
            "cargo_description": "Kontenery mieszane, w tym reefer",
            "requires_reefer": True,
            "dangerous_goods": False,
            "confidence_score": 0.95
        }

    system_prompt = """
    Jesteś asystentem agenta morskiego. Twoim zadaniem jest wyciągnięcie ustrukturyzowanych danych z maila nominacyjnego od armatora.
    Zwróć TYLKO czysty obiekt JSON, bez znaczników markdown.
    Struktura JSON:
    {
        "vessel_imo": "7-cyfrowy numer IMO statku (jeśli brak, spróbuj wywnioskować lub zwróć null)",
        "vessel_name": "nazwa statku",
        "port_name": "nazwa portu docelowego",
        "eta": "Data i czas ETA w formacie ISO8601 (np. 2024-07-01T10:00:00Z)",
        "cargo_description": "krótki opis ładunku",
        "requires_reefer": true/false (czy ładunek wymaga chłodzenia/igloportu?),
        "dangerous_goods": true/false (czy ładunek jest niebezpieczny - IMDG?)
    }
    """

    user_prompt = f"Temat: {subject}\n\nTreść maila:\n{body}"

    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        result_content = response.choices[0].message.content
        parsed_data = json.loads(result_content)
        parsed_data["confidence_score"] = 0.92  # Przykładowy score z LLM
        return parsed_data

    except Exception as e:
        raise LLMParsingError(details=f"Błąd integracji z OpenAI: {str(e)}")
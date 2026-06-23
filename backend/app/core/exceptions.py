from typing import Any, Dict, Optional


class AppException(Exception):
    """Bazowa klasa dla wszystkich niestandardowych wyjątków w SentiPort."""

    def __init__(self, message: str, status_code: int = 400, payload: Optional[Dict[str, Any]] = None):
        self.message = message
        self.status_code = status_code
        self.payload = payload


class EntityNotFoundError(AppException):
    def __init__(self, entity_name: str, entity_id: Any = None):
        msg = f"Nie znaleziono: {entity_name}"
        if entity_id:
            msg += f" o identyfikatorze {entity_id}"
        super().__init__(message=msg, status_code=404)


class LLMParsingError(AppException):
    def __init__(self, details: str):
        super().__init__(
            message="Błąd przetwarzania tekstu przez model AI (LLM).",
            status_code=422,
            payload={"details": details}
        )


class RiskCalculationError(AppException):
    def __init__(self, details: str):
        super().__init__(
            message="Wystąpił problem podczas kalkulacji wyniku ryzyka w bazie.",
            status_code=500,
            payload={"details": details}
        )


class DatabaseConstraintError(AppException):
    def __init__(self, details: str):
        super().__init__(
            message="Konflikt w bazie danych (np. duplikat lub brak powiązania).",
            status_code=409,
            payload={"details": details}
        )
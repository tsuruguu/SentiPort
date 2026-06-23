from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
import logging

from app.core.exceptions import AppException

# Prosty logger, żeby błędy 500 widać było w terminalu Dockera
logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """Łapie nasze własne błędy biznesowe (np. LLMParsingError)."""
        content = {"error": exc.message}
        if exc.payload:
            content["details"] = exc.payload
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(IntegrityError)
    async def sqlalchemy_integrity_error_handler(request: Request, exc: IntegrityError):
        """
        Kluczowe na hakatonie! Łapie błędy bazy (np. naruszenie klucza obcego),
        zamiast wywalać stronę z kodem 500 i surowym SQLem.
        """
        logger.error(f"Integrity Error: {exc}")
        return JSONResponse(
            status_code=409,
            content={
                "error": "Konflikt danych. Prawdopodobnie taki rekord już istnieje lub brakuje powiązanego zasobu."
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Ostatnia deska ratunku - łapie wszystkie inne, nieprzewidziane crashe."""
        logger.error(f"Unhandled Exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Wystąpił nieoczekiwany błąd serwera. Sprawdź logi."}
        )
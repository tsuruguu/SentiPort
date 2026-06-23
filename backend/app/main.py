from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importy naszych modułów
from app.config import settings
from app.api.v1.router import api_router
from app.core.exception_handlers import register_exception_handlers

# Inicjalizacja instancji FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Automatyzacja procesu nominacji armatorskich (RedSky AI / MAG). Agent morski napędzany AI."
)

# Konfiguracja CORS - na hakatonie wpuszczamy wszystkich (strony, Postmana, dockera)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Podpinamy łapacze błędów z naszego folderu core/
register_exception_handlers(app)

@app.get("/health", tags=["System"])
def health_check():
    """Endpoint sprawdzający, czy serwer żyje."""
    return {
        "status": "ok",
        "message": "SentiPort Backend is running!",
        "project": settings.PROJECT_NAME
    }

# Podpinamy CAŁE drzewo naszych endpointów (vessels, ports, risk, nominations)
app.include_router(api_router, prefix=settings.API_V1_STR)

from fastapi import BackgroundTasks


@app.on_event("startup")
def startup_event():
    # Odpalamy generator 50 nominacji w tle przy starcie serwera
    from app.database import SessionLocal
    from seed.seed_data import seed_additional_nominations

    db = SessionLocal()
    try:
        seed_additional_nominations(db, count=50)
    finally:
        db.close()
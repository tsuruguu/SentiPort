from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="Automatyzacja procesu nominacji armatorskich (RedSky AI / MAG)"
)

# Konfiguracja CORS (na hackathonie pozwalamy na wszystko)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "message": "SentiPort Backend is running!",
        "project": settings.PROJECT_NAME
    }

# TODO: Tutaj podepniemy routery (API), jak tylko je stworzymy
# from app.api.v1.router import api_router
# app.include_router(api_router, prefix=settings.API_V1_STR)
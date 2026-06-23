from fastapi import APIRouter
from app.api.v1 import nominations, companies, ports, vessels, risk, documents, port_calls

api_router = APIRouter()

api_router.include_router(nominations.router, prefix="/nominations", tags=["Nominations"])
api_router.include_router(companies.router, prefix="/companies", tags=["Companies"])
api_router.include_router(ports.router, prefix="/ports", tags=["Ports & Berths"])
api_router.include_router(vessels.router, prefix="/vessels", tags=["Vessels Fleet"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk Intelligence"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documentation"])
api_router.include_router(port_calls.router, prefix="/port-calls", tags=["Port Operations"])
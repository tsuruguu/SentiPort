from fastapi import APIRouter
from app.schemas.common import MessageResponse

router = APIRouter()

@router.get("/active", response_model=MessageResponse)
def get_active_port_calls():
    """Pobiera harmonogram aktywnych wizyt w porcie."""
    return {"message": "Brak aktywnych wizyt w porcie na ten moment."}
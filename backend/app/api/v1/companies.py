from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.api import deps
from app.schemas.company import CompanyResponse
from app.models.company import Company

router = APIRouter()

@router.get("/", response_model=List[CompanyResponse])
def get_companies(db: Session = Depends(deps.get_db)):
    """Pobiera listę wszystkich firm (armatorów, operatorów)."""
    return db.query(Company).all()
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any

from app.api import deps
from app.schemas.nomination import EmailPayload, NominationResponse
from app.models.operations import Nomination
from app.models.vessel import Vessel
from app.models.company import Company
from app.models.reference import Port

router = APIRouter()

@router.post("/parse-email", response_model=NominationResponse, status_code=status.HTTP_201_CREATED)
def parse_nomination_email(
        payload: EmailPayload,
        db: Session = Depends(deps.get_db)
) -> Any:
    # 1. Pobranie danych startowych (tzw. "safe guard")
    dummy_vessel = db.query(Vessel).first()
    dummy_company = db.query(Company).first()
    dummy_port = db.query(Port).first()

    if not dummy_vessel or not dummy_company or not dummy_port:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Brak danych startowych w bazie!"
        )

    # 2. Tworzenie obiektu modelu
    new_nomination = Nomination(
        vessel_id=dummy_vessel.vessel_id,
        nominating_company_id=dummy_company.company_id,
        destination_port_id=dummy_port.port_id,
        source_email_subject=payload.subject,
        source_email_body_raw=payload.body,
        status="received",
        assigned_agent_name="Agent Hakatonowy"
    )

    # 3. Zapis do bazy
    db.add(new_nomination)
    db.commit()
    # 4. Odświeżenie, żeby obiekt miał ID z bazy!
    db.refresh(new_nomination)

    return new_nomination
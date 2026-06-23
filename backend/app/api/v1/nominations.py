from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any
import uuid

from app.api import deps
from app.schemas.nomination import EmailPayload, NominationResponse
from app.models.operations import Nomination
from app.models.vessel import Vessel
from app.models.company import Company
from app.models.reference import Port
from app.services import agent_extraction_service

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


@router.post("/{nomination_id}/extract", response_model=NominationResponse, status_code=status.HTTP_200_OK)
def extract_nomination_data(
        nomination_id: uuid.UUID,
        db: Session = Depends(deps.get_db)
) -> Any:
    """
    Wysyła treść maila istniejącej nominacji do agenta ekstrakcji
    (wrapper kolegi na ElevenLabs), a zwrócone dane (statek, port,
    ładunek, firma, kontakt) dociąga do istniejących rekordów w bazie
    i zapisuje wynik w nominacji.

    Typowy przepływ: POST /mailbox/sync-inbox (import maila) ->
    POST /nominations/{id}/extract (ekstrakcja przez agenta) ->
    przegląd w UI.

    Błędy biznesowe (nominacja nie istnieje, agent nieosiągalny, agent
    zwrócił niepoprawny JSON) są obsługiwane globalnie przez
    register_exception_handlers - tutaj nie trzeba ich łapać.
    """
    return agent_extraction_service.extract_and_apply(db, nomination_id)
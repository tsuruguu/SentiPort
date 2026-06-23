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
    """
    Główny punkt wejścia: odbiera maila od armatora, (wkrótce) parsuje przez AI i zapisuje do bazy.
    """

    # Hakatonowy ratunek: żeby baza nie rzuciła błędem Foreign Key (brak statku),
    # dopóki LLM nie wyciągnie poprawnego IMO Number, łapiemy "na twardo" statki i firmy z seeda.
    dummy_vessel = db.query(Vessel).first()
    dummy_company = db.query(Company).first()
    dummy_port = db.query(Port).first()

    if not dummy_vessel or not dummy_company or not dummy_port:
        raise HTTPException(
            status_code=500,
            detail="Brak danych startowych w bazie! Uruchom najpierw plik baza.sql"
        )

    # TODO: W następnym kroku odpalimy tu llm_parser_service, który:
    # 1. Wyciągnie nazwę statku, ładunek i port docelowy.
    # 2. Nadpisze te 'dummy' wartości prawdziwymi z bazy.

    new_nomination = Nomination(
        vessel_id=dummy_vessel.vessel_id,
        nominating_company_id=dummy_company.company_id,
        destination_port_id=dummy_port.port_id,
        source_email_subject=payload.subject,
        source_email_body_raw=payload.body,
        # Flaga, że przyjęliśmy, ale jeszcze nie przepuściliśmy przez LLM (zmienimy to za chwilę)
        status="received",
        assigned_agent_name="Agent Hakatonowy"
    )

    db.add(new_nomination)
    db.commit()
    db.refresh(new_nomination)

    return new_nomination
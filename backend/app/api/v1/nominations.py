from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Any, Optional
import uuid

from app.api import deps
from app.schemas.nomination import EmailPayload, NominationResponse
from app.schemas.nomination_detail import NominationListResponse, NominationDetailResponse, \
    BerthRecommendationListResponse, BerthRecommendationResponse, BerthSummary
from app.models.operations import Nomination
from app.models.vessel import Vessel
from app.models.company import Company
from app.models.reference import Port
from app.models.enums import NominationStatus
from app.services import agent_extraction_service, nomination_view_service, berth_assignment_service
from app.repositories import nomination_repository

router = APIRouter()


@router.get("/", response_model=NominationListResponse, status_code=status.HTTP_200_OK)
def list_nominations(
        status_filter: Optional[NominationStatus] = Query(None, alias="status"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
        db: Session = Depends(deps.get_db),
) -> Any:
    """
    Lista nominacji do widoku głównego UI - najnowsze pierwsze.
    Opcjonalny filtr ?status=parsed_pending_review np. żeby agent
    portowy widział tylko te czekające na jego przegląd.
    """
    return nomination_view_service.list_nominations(db, status=status_filter, limit=limit, offset=offset)


@router.get("/{nomination_id}", response_model=NominationDetailResponse, status_code=status.HTTP_200_OK)
def get_nomination_detail(
        nomination_id: uuid.UUID,
        db: Session = Depends(deps.get_db),
) -> Any:
    """
    Pełny widok jednej nominacji do ekranu szczegółów/weryfikacji:
    statek + jego wymiary, firma, kontakt, port, nabrzeże żądane vs
    przydzielone, wszystkie pozycje ładunku, usługi portowe, notatki
    wymagające przeglądu i metadane załączników.
    """
    detail = nomination_view_service.get_nomination_detail(db, nomination_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nominacja nie istnieje")
    return detail


@router.get("/{nomination_id}/attachments/{attachment_id}/download")
def download_attachment(
        nomination_id: uuid.UUID,
        attachment_id: uuid.UUID,
        db: Session = Depends(deps.get_db),
) -> Response:
    """
    Pobiera surową treść załącznika (np. PDF nominacji) zapisanego w
    bazie. Sprawdza, że attachment faktycznie należy do podanej
    nominacji - żeby nie dało się podglądać plików z innej nominacji
    znając tylko attachment_id.
    """
    attachment = nomination_repository.get_attachment_by_id(db, attachment_id)
    if not attachment or attachment.nomination_id != nomination_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Załącznik nie istnieje")

    return Response(
        content=bytes(attachment.file_data),
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'inline; filename="{attachment.filename}"'},
    )


@router.get("/{nomination_id}/recommended-berths", response_model=BerthRecommendationListResponse,
           status_code=status.HTTP_200_OK)
def get_recommended_berths(
        nomination_id: uuid.UUID,
        top_n: int = Query(3, ge=1, le=10),
        db: Session = Depends(deps.get_db),
) -> Any:
    """
    TOP-N nabrzeż (domyślnie 3) zalecanych dla tej nominacji w jej porcie
    docelowym, posortowanych od najlepszego dopasowania.

    Bezwzględne wymogi bezpieczeństwa (zanurzenie/LOA/DWT statku,
    obsługa ładunku niebezpiecznego/reefer, brak kolizji czasowej z
    inną rezerwacją) CAŁKOWICIE wykluczają nabrzeże z listy - jeśli
    żadne nabrzeże w porcie nie spełnia tych wymogów, lista będzie
    krótsza niż top_n (nawet pusta), z ostrzeżeniem w polu `warning`.
    """
    nomination = nomination_repository.get_nomination(db, nomination_id)
    if not nomination:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nominacja nie istnieje")

    candidates = berth_assignment_service.recommend_berths_for_nomination(db, nomination, top_n=top_n)

    warning = None
    if len(candidates) < top_n:
        warning = (
            f"Znaleziono tylko {len(candidates)} z {top_n} żądanych nabrzeż spełniających wymogi "
            f"bezpieczeństwa dla tego statku/ładunku - może być wymagana ręczna weryfikacja przez agenta portowego."
        )

    return BerthRecommendationListResponse(
        nomination_id=nomination_id,
        recommendations=[
            BerthRecommendationResponse(
                berth=BerthSummary.model_validate(c.berth),
                score=round(c.score, 2),
                reasons=c.reasons,
            )
            for c in candidates
        ],
        warning=warning,
    )


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
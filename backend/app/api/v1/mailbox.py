from fastapi import APIRouter, HTTPException, status
from typing import Any

from app.schemas.mailbox import SyncInboxRequest, SyncInboxResponse
from app.services import email_sync_service

router = APIRouter()


@router.post("/sync-inbox", response_model=SyncInboxResponse, status_code=status.HTTP_200_OK)
def sync_inbox(payload: SyncInboxRequest) -> Any:
    """
    Importuje nowe maile ze skrzynki IMAP (np. agent@sentiport.pl) do
    tabeli `nominations`.

    Bezpiecznie klikalne wielokrotnie: każdy mail ma trwały email_hash
    (treść + nadawca + data) zarówno sprawdzany w aplikacji, jak i
    chroniony UNIQUE constraintem w bazie. Dodatkowo, po imporcie mail
    jest przenoszony z INBOX do folderu "Imported" na serwerze IMAP, więc
    fizycznie nie może zostać zaimportowany drugi raz - nawet jeśli ktoś
    kliknie ten endpoint wiele razy pod rząd lub ręcznie przywróci flagę
    "nieprzeczytany" na mailu.

    Zwraca podsumowanie z trzema listami: imported / skipped_duplicates /
    failed, żeby UI mogło pokazać dokładnie co się stało przy danym
    kliknięciu (a nie tylko zbiorczy licznik).
    """
    try:
        summary = email_sync_service.sync_emails(
            imap_host=payload.imap_host,
            user=payload.user,
            password=payload.password,
            port=payload.imap_port,
        )
    except Exception as exc:
        # Błędy połączenia z IMAP (zły host/port/login) - to nie jest
        # błąd biznesowy aplikacji, więc zwracamy jasny 502.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Nie udało się połączyć ze skrzynką IMAP: {exc}",
        )

    return SyncInboxResponse(
        imported_count=len(summary["imported"]),
        skipped_duplicates_count=len(summary["skipped_duplicates"]),
        failed_count=len(summary["failed"]),
        imported=summary["imported"],
        skipped_duplicates=summary["skipped_duplicates"],
        failed=summary["failed"],
    )
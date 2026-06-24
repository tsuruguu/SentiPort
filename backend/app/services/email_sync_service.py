import hashlib
import logging
from imap_tools import MailBoxUnencrypted, AND
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models.operations import Nomination, NominationAttachment
from app.models.vessel import Vessel
from app.models.company import Company
from app.models.reference import Port

logger = logging.getLogger(__name__)

# Folder, do którego przenosimy maile PO udanym imporcie do bazy.
# Dzięki temu "drugi klik" / ponowne oznaczenie maila jako nieprzeczytany
# w INBOX nigdy nie spowoduje powtórnego importu - mail fizycznie nie jest
# już w INBOX.
IMPORTED_FOLDER = "Imported"
FAILED_FOLDER = "ImportFailed"

# Tylko te typy załączników zapisujemy jako attachment nominacji - inne
# (np. obrazki w stopce maila, podpisy graficzne) są ignorowane, żeby nie
# zaśmiecać bazy.
ACCEPTED_ATTACHMENT_CONTENT_TYPES = {"application/pdf"}


def get_email_hash(subject: str, body: str, sender: str, date) -> str:
    """
    Hash jednoznacznie identyfikujący treść maila.
    Używany jako 'odcisk palca' do deduplikacji - niezależnie od tego,
    ile razy mail zostanie zaimportowany/kliknięty, hash będzie identyczny.
    """
    raw = f"{subject}|{body}|{sender}|{date}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure_folder(mailbox: MailBoxUnencrypted, folder_name: str) -> None:
    """Tworzy folder IMAP, jeśli jeszcze nie istnieje."""
    existing = {f.name for f in mailbox.folder.list()}
    if folder_name not in existing:
        mailbox.folder.create(folder_name)


def _save_attachments(db, nomination_id, attachments) -> int:
    """
    Zapisuje załączniki PDF maila jako wiersze w nomination_attachments.

    Deduplikacja: hash SHA-256 treści pliku + UNIQUE(nomination_id,
    file_hash_sha256) w bazie - jeśli ten sam plik trafiłby tu drugi raz
    (np. przy ponownym uruchomieniu sync na tym samym mailu w trakcie
    debugowania), insert po prostu się nie powtórzy.

    Inne typy plików niż PDF (np. obrazki w stopce maila) są ignorowane -
    patrz ACCEPTED_ATTACHMENT_CONTENT_TYPES.

    Zwraca liczbę faktycznie zapisanych załączników.
    """
    saved_count = 0
    for att in attachments:
        if att.content_type not in ACCEPTED_ATTACHMENT_CONTENT_TYPES:
            logger.info("Pomijam załącznik '%s' - nieobsługiwany typ %s.", att.filename, att.content_type)
            continue

        file_hash = hashlib.sha256(att.payload).hexdigest()
        attachment = NominationAttachment(
            nomination_id=nomination_id,
            filename=att.filename or "attachment.pdf",
            content_type=att.content_type,
            file_size_bytes=len(att.payload),
            file_data=att.payload,
            file_hash_sha256=file_hash,
        )
        try:
            db.add(attachment)
            db.flush()  # wymusza sprawdzenie UNIQUE constraint już teraz, bez czekania na końcowy commit
            saved_count += 1
        except IntegrityError:
            # Duplikat tego samego pliku dla tej samej nominacji - pomijamy.
            db.rollback()
            logger.info("Załącznik '%s' (hash=%s) już istnieje dla tej nominacji, pomijam.", att.filename, file_hash[:8])

    return saved_count


def sync_emails(imap_host: str, user: str, password: str, port: int = 143) -> dict:
    """
    Importuje nowe maile ze skrzynki IMAP do tabeli `nominations`.

    Zabezpieczenia przed podwójnym importem (nawet jeśli ktoś kliknie
    "Importuj" wielokrotnie albo zrestartuje sync w trakcie):
      1. email_hash (treść+nadawca+data) sprawdzany PRZED zapisem.
      2. email_hash ma UNIQUE constraint w bazie -> nawet wyścig (race
         condition) między dwoma równoległymi requestami zostanie
         odrzucony przez bazę, a nie tylko przez kod aplikacji.
      3. Po udanym imporcie mail jest PRZENOSZONY z INBOX do folderu
         "Imported" - więc fizycznie nie ma go już tam, gdzie sync szuka
         nowych maili. To działa nawet jeśli ktoś ręcznie oznaczy maila
         jako "nieprzeczytany" ponownie.
      4. Błąd przy jednym mailu (np. zły encoding) nie przerywa całej
         paczki - leci do folderu "ImportFailed" i sync kontynuuje dalej.

    Zwraca podsumowanie: ile zaimportowano, ile pominięto (duplikaty),
    ile się nie powiodło.
    """
    db = SessionLocal()
    summary = {"imported": [], "skipped_duplicates": [], "failed": []}

    # Zakładamy, że zawsze mapujemy na pierwszy lepszy statek/port/firmę
    # dla testów - to zostanie zastąpione realnym dociąganiem danych
    # w kolejnym kroku (parsowanie treści maila).
    default_vessel = db.query(Vessel).first()
    default_port = db.query(Port).first()
    default_company = db.query(Company).first()

    try:
        # MailBoxUnencrypted (nie MailBox!) - klasa MailBox z imap_tools
        # ZAWSZE owija połączenie w SSL/TLS niezależnie od podanego portu,
        # co na plain IMAP (port 143, bez wymuszonego szyfrowania - tak
        # skonfigurowany jest nasz docker-mailserver) kończy się błędem
        # "[SSL: WRONG_VERSION_NUMBER]" - serwer odpowiada zwykłym
        # plain-text greeting, a klient czeka na TLS handshake.
        with MailBoxUnencrypted(imap_host, port=port).login(user, password) as mailbox:
            _ensure_folder(mailbox, IMPORTED_FOLDER)
            _ensure_folder(mailbox, FAILED_FOLDER)

            # Pobieramy WSZYSTKIE maile z INBOX, niezależnie od flagi
            # seen/unseen - jedynym źródłem prawdy o tym "czy już
            # zaimportowany" jest email_hash w bazie + fakt, że mail
            # zaimportowany fizycznie nie siedzi już w INBOX.
            messages = list(mailbox.fetch(AND(all=True)))

            for msg in messages:
                email_hash = get_email_hash(msg.subject, msg.text, msg.from_, str(msg.date))

                # --- Warstwa 1: sprawdzenie w aplikacji ---
                if db.query(Nomination).filter(Nomination.email_hash == email_hash).first():
                    logger.info("Mail '%s' (hash=%s) już istnieje w bazie, pomijam.", msg.subject, email_hash[:8])
                    summary["skipped_duplicates"].append(msg.subject)
                    # Mail jest duplikatem (np. zaimportowany wcześniej, a
                    # potem ktoś ręcznie cofnął go do INBOX) - i tak go
                    # sprzątamy z INBOX, żeby nie zaśmiecał kolejnych syncow.
                    mailbox.move(msg.uid, IMPORTED_FOLDER)
                    continue

                new_nom = Nomination(
                    vessel_id=default_vessel.vessel_id if default_vessel else None,
                    destination_port_id=default_port.port_id if default_port else None,
                    nominating_company_id=default_company.company_id if default_company else None,
                    source_email_subject=msg.subject,
                    source_email_body_raw=msg.text,
                    source_email_received_at=msg.date,
                    source_email_sender_address=msg.from_,
                    email_hash=email_hash,
                    status="received",
                    assigned_agent_name="Agent Hakatonowy",
                )

                try:
                    db.add(new_nom)
                    # --- Warstwa 2: ochrona na poziomie bazy (UNIQUE) ---
                    db.commit()
                except IntegrityError:
                    # Ktoś inny (np. równoległy request) zdążył zaimportować
                    # ten sam mail między naszym sprawdzeniem a commitem.
                    db.rollback()
                    logger.info("Mail '%s' zaimportowany równolegle przez inny proces, pomijam.", msg.subject)
                    summary["skipped_duplicates"].append(msg.subject)
                    mailbox.move(msg.uid, IMPORTED_FOLDER)
                    continue
                except Exception as exc:
                    db.rollback()
                    logger.exception("Błąd importu maila '%s'", msg.subject)
                    summary["failed"].append({"subject": msg.subject, "error": str(exc)})
                    mailbox.move(msg.uid, FAILED_FOLDER)
                    continue

                # Sukces: mail trwale zapisany w bazie -> wyprowadzamy go
                # z INBOX, żeby fizycznie nie mógł zostać zaimportowany
                # drugi raz, nawet po przywróceniu flagi "unseen".
                mailbox.move(msg.uid, IMPORTED_FOLDER)

                # Załączniki zapisujemy PO udanym commicie nominacji, bo
                # wymagają już istniejącego nomination_id (FK NOT NULL).
                attachments_saved = _save_attachments(db, new_nom.nomination_id, msg.attachments)
                if attachments_saved:
                    db.commit()

                logger.info("Zaimportowano mail: '%s' -> nomination_id=%s (załączników: %d)",
                           msg.subject, new_nom.nomination_id, attachments_saved)
                summary["imported"].append({
                    "subject": msg.subject,
                    "nomination_id": str(new_nom.nomination_id),
                    "attachments_saved": attachments_saved,
                })

    finally:
        db.close()

    return summary
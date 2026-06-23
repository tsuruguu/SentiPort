from unittest.mock import MagicMock, patch
from sqlalchemy.exc import IntegrityError

from app.services import email_sync_service


def _make_fake_msg(uid, subject, text, from_, date="2026-06-23", attachments=None):
    msg = MagicMock()
    msg.uid = uid
    msg.subject = subject
    msg.text = text
    msg.from_ = from_
    msg.date = date
    msg.attachments = attachments or []
    return msg


def _make_fake_attachment(filename, content_type="application/pdf", payload=b"%PDF-1.4 fake content"):
    att = MagicMock()
    att.filename = filename
    att.content_type = content_type
    att.payload = payload
    return att


class FakeFolderInfo:
    def __init__(self, name):
        self.name = name


@patch("app.services.email_sync_service.SessionLocal")
@patch("app.services.email_sync_service.MailBox")
def test_sync_emails_imports_new_mail_once(mock_mailbox_cls, mock_session_local):
    """Nowy mail (hash nie istnieje w bazie) powinien zostać zaimportowany
    i przeniesiony do folderu Imported."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    # Brak duplikatu w bazie
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.query.return_value.first.return_value = None  # default vessel/port/company = None

    mock_mailbox = MagicMock()
    mock_mailbox_cls.return_value.login.return_value.__enter__.return_value = mock_mailbox
    mock_mailbox.folder.list.return_value = [FakeFolderInfo("INBOX")]

    msg = _make_fake_msg("1", "Nominacja MV Test", "Treść testowa", "armator1@armatorzy.pl")
    mock_mailbox.fetch.return_value = [msg]

    summary = email_sync_service.sync_emails("mailserver", "agent@sentiport.pl", "haslo123")

    assert len(summary["imported"]) == 1
    assert summary["imported"][0]["subject"] == "Nominacja MV Test"
    assert summary["skipped_duplicates"] == []
    assert summary["failed"] == []
    # Mail MUSI zostać przeniesiony z INBOX po imporcie
    mock_mailbox.move.assert_called_once_with("1", email_sync_service.IMPORTED_FOLDER)
    mock_db.commit.assert_called_once()


@patch("app.services.email_sync_service.SessionLocal")
@patch("app.services.email_sync_service.MailBox")
def test_sync_emails_skips_application_level_duplicate(mock_mailbox_cls, mock_session_local):
    """Jeśli hash maila już istnieje w bazie, mail NIE jest zapisywany
    drugi raz, ale i tak jest sprzątany z INBOX."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    # Symulujemy, że taki email_hash już istnieje
    existing_nomination = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing_nomination
    mock_db.query.return_value.first.return_value = None

    mock_mailbox = MagicMock()
    mock_mailbox_cls.return_value.login.return_value.__enter__.return_value = mock_mailbox
    mock_mailbox.folder.list.return_value = [FakeFolderInfo("INBOX")]

    msg = _make_fake_msg("2", "Nominacja MV Test", "Treść testowa", "armator1@armatorzy.pl")
    mock_mailbox.fetch.return_value = [msg]

    summary = email_sync_service.sync_emails("mailserver", "agent@sentiport.pl", "haslo123")

    assert summary["imported"] == []
    assert summary["skipped_duplicates"] == ["Nominacja MV Test"]
    # Mail i tak zostaje wyprowadzony z INBOX, mimo że jest duplikatem
    mock_mailbox.move.assert_called_once_with("2", email_sync_service.IMPORTED_FOLDER)
    # Nigdy nie próbujemy zapisać duplikatu
    mock_db.add.assert_not_called()


@patch("app.services.email_sync_service.SessionLocal")
@patch("app.services.email_sync_service.MailBox")
def test_sync_emails_handles_race_condition_integrity_error(mock_mailbox_cls, mock_session_local):
    """Jeśli baza odrzuci zapis przez UNIQUE constraint (race condition -
    dwa równoległe sync'i złapały ten sam mail), nie wywalamy całego
    importu, tylko traktujemy to jako duplikat."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.query.return_value.first.return_value = None
    mock_db.commit.side_effect = IntegrityError("stmt", "params", "orig")

    mock_mailbox = MagicMock()
    mock_mailbox_cls.return_value.login.return_value.__enter__.return_value = mock_mailbox
    mock_mailbox.folder.list.return_value = [FakeFolderInfo("INBOX")]

    msg = _make_fake_msg("3", "Nominacja MV Race", "Treść testowa", "armator2@armatorzy.pl")
    mock_mailbox.fetch.return_value = [msg]

    summary = email_sync_service.sync_emails("mailserver", "agent@sentiport.pl", "haslo123")

    assert summary["imported"] == []
    assert summary["skipped_duplicates"] == ["Nominacja MV Race"]
    mock_db.rollback.assert_called_once()
    mock_mailbox.move.assert_called_once_with("3", email_sync_service.IMPORTED_FOLDER)


@patch("app.services.email_sync_service.SessionLocal")
@patch("app.services.email_sync_service.MailBox")
def test_sync_emails_continues_after_unexpected_error(mock_mailbox_cls, mock_session_local):
    """Nieoczekiwany błąd przy jednym mailu (np. zły encoding) nie
    przerywa importu pozostałych maili w paczce - mail trafia do
    ImportFailed, a sync kontynuuje."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.query.return_value.first.return_value = None
    # Pierwszy commit wybucha nieoczekiwanym błędem, drugi się udaje
    mock_db.commit.side_effect = [RuntimeError("boom"), None]

    mock_mailbox = MagicMock()
    mock_mailbox_cls.return_value.login.return_value.__enter__.return_value = mock_mailbox
    mock_mailbox.folder.list.return_value = [FakeFolderInfo("INBOX")]

    msg_bad = _make_fake_msg("4", "Zepsuty mail", "...", "armator3@armatorzy.pl")
    msg_good = _make_fake_msg("5", "Dobry mail", "...", "armator3@armatorzy.pl")
    mock_mailbox.fetch.return_value = [msg_bad, msg_good]

    summary = email_sync_service.sync_emails("mailserver", "agent@sentiport.pl", "haslo123")

    assert len(summary["failed"]) == 1
    assert summary["failed"][0]["subject"] == "Zepsuty mail"
    assert len(summary["imported"]) == 1
    assert summary["imported"][0]["subject"] == "Dobry mail"
    mock_mailbox.move.assert_any_call("4", email_sync_service.FAILED_FOLDER)
    mock_mailbox.move.assert_any_call("5", email_sync_service.IMPORTED_FOLDER)


@patch("app.services.email_sync_service.SessionLocal")
@patch("app.services.email_sync_service.MailBox")
def test_sync_emails_creates_missing_folders(mock_mailbox_cls, mock_session_local):
    """Jeśli foldery Imported/ImportFailed nie istnieją jeszcze na
    serwerze IMAP, sync powinien je utworzyć zamiast wybuchać."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.query.return_value.first.return_value = None

    mock_mailbox = MagicMock()
    mock_mailbox_cls.return_value.login.return_value.__enter__.return_value = mock_mailbox
    mock_mailbox.folder.list.return_value = [FakeFolderInfo("INBOX")]  # brak Imported/ImportFailed
    mock_mailbox.fetch.return_value = []

    email_sync_service.sync_emails("mailserver", "agent@sentiport.pl", "haslo123")

    created_folders = {call.args[0] for call in mock_mailbox.folder.create.call_args_list}
    assert created_folders == {
        email_sync_service.IMPORTED_FOLDER,
        email_sync_service.FAILED_FOLDER,
    }


def test_save_attachments_persists_pdf():
    mock_db = MagicMock()
    nomination_id = "fake-nomination-id"
    att = _make_fake_attachment("nominacja.pdf")

    saved_count = email_sync_service._save_attachments(mock_db, nomination_id, [att])

    assert saved_count == 1
    mock_db.add.assert_called_once()
    saved_obj = mock_db.add.call_args.args[0]
    assert saved_obj.filename == "nominacja.pdf"
    assert saved_obj.content_type == "application/pdf"
    assert saved_obj.nomination_id == nomination_id
    assert saved_obj.file_data == b"%PDF-1.4 fake content"
    assert len(saved_obj.file_hash_sha256) == 64  # sha256 hex digest


def test_save_attachments_skips_non_pdf():
    """Obrazki w stopce maila (np. logo firmy) nie powinny być zapisywane
    jako attachment nominacji - tylko PDF nas interesuje."""
    mock_db = MagicMock()
    att = _make_fake_attachment("logo.png", content_type="image/png")

    saved_count = email_sync_service._save_attachments(mock_db, "fake-nomination-id", [att])

    assert saved_count == 0
    mock_db.add.assert_not_called()


def test_save_attachments_deduplicates_on_integrity_error():
    """Jeśli baza odrzuci zapis przez UNIQUE(nomination_id, file_hash_sha256)
    (ten sam plik już zapisany dla tej nominacji), traktujemy to jako
    duplikat, nie jako błąd - kontynuujemy z pozostałymi załącznikami."""
    mock_db = MagicMock()
    mock_db.flush.side_effect = [IntegrityError("stmt", "params", "orig"), None]

    att_duplicate = _make_fake_attachment("nominacja.pdf")
    att_new = _make_fake_attachment("specyfikacja.pdf", payload=b"%PDF-1.4 inna zawartosc")

    saved_count = email_sync_service._save_attachments(mock_db, "fake-nomination-id", [att_duplicate, att_new])

    assert saved_count == 1  # tylko drugi plik się zapisał
    mock_db.rollback.assert_called_once()


def test_save_attachments_handles_multiple_pdfs_in_one_mail():
    """Jeden mail może mieć kilka załączników PDF na raz - wszystkie
    powinny się zapisać jako osobne wiersze."""
    mock_db = MagicMock()
    attachments = [
        _make_fake_attachment("nominacja.pdf", payload=b"plik 1"),
        _make_fake_attachment("manifest_ladunku.pdf", payload=b"plik 2"),
    ]

    saved_count = email_sync_service._save_attachments(mock_db, "fake-nomination-id", attachments)

    assert saved_count == 2
    assert mock_db.add.call_count == 2


@patch("app.services.email_sync_service.SessionLocal")
@patch("app.services.email_sync_service.MailBox")
def test_sync_emails_saves_pdf_attachment_with_new_nomination(mock_mailbox_cls, mock_session_local):
    """Test end-to-end: mail z załącznikiem PDF powinien zaimportować
    nominację ORAZ zapisać załącznik, z dodatkowym commitem."""
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.query.return_value.first.return_value = None

    mock_mailbox = MagicMock()
    mock_mailbox_cls.return_value.login.return_value.__enter__.return_value = mock_mailbox
    mock_mailbox.folder.list.return_value = [FakeFolderInfo("INBOX")]

    att = _make_fake_attachment("nominacja.pdf")
    msg = _make_fake_msg("1", "Nominacja z PDF", "Treść", "armator1@armatorzy.pl", attachments=[att])
    mock_mailbox.fetch.return_value = [msg]

    summary = email_sync_service.sync_emails("mailserver", "agent@sentiport.pl", "haslo123")

    assert len(summary["imported"]) == 1
    assert summary["imported"][0]["attachments_saved"] == 1
    # commit wywołany dwa razy: raz dla nominacji, raz po zapisaniu załącznika
    assert mock_db.commit.call_count == 2
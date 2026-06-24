import uuid
from unittest.mock import MagicMock

from app.repositories import document_repository
from app.models.enums import DocumentType


def test_save_generated_document_first_version_is_one():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.count.return_value = 0

    nomination_id = uuid.uuid4()
    document_repository.save_generated_document(
        mock_db, nomination_id=nomination_id, document_type=DocumentType.port_entry_notification,
        filename="test.pdf", file_data=b"%PDF-1.4", file_hash_sha256="a" * 64,
    )

    saved_doc = mock_db.add.call_args.args[0]
    assert saved_doc.version_number == 1
    assert saved_doc.nomination_id == nomination_id
    mock_db.commit.assert_called_once()


def test_save_generated_document_increments_version_when_previous_exists():
    """Jeśli dla tej nominacji już istnieją 2 wcześniejsze wersje tego
    typu dokumentu, nowa powinna dostać version_number=3 - poprzednie
    NIE są usuwane (pełny audyt historii wersji)."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.count.return_value = 2

    document_repository.save_generated_document(
        mock_db, nomination_id=uuid.uuid4(), document_type=DocumentType.port_entry_notification,
        filename="test_v3.pdf", file_data=b"%PDF-1.4", file_hash_sha256="b" * 64,
    )

    saved_doc = mock_db.add.call_args.args[0]
    assert saved_doc.version_number == 3


def test_get_document_by_id_returns_none_when_missing():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    result = document_repository.get_document_by_id(mock_db, uuid.uuid4())

    assert result is None


def test_get_documents_for_nomination_orders_by_newest_first():
    mock_db = MagicMock()
    mock_query = mock_db.query.return_value.filter.return_value.order_by.return_value
    mock_query.all.return_value = ["doc2", "doc1"]

    result = document_repository.get_documents_for_nomination(mock_db, uuid.uuid4())

    assert result == ["doc2", "doc1"]
    mock_db.query.return_value.filter.return_value.order_by.assert_called_once()
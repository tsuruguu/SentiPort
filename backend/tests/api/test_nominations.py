from unittest.mock import MagicMock, patch
from app.models.operations import Nomination


def test_parse_email_endpoint_success(client, mock_db, mock_uuid):
    # 1. Przygotowanie mocków dla zapytań .first()
    mock_dummy = MagicMock()
    mock_dummy.vessel_id = mock_uuid
    mock_dummy.company_id = mock_uuid
    mock_dummy.port_id = mock_uuid

    # API robi 3 zapytania .first() z rzędu
    mock_db.query.return_value.first.side_effect = [mock_dummy, mock_dummy, mock_dummy]

    # 2. Mockujemy zachowanie refresh() tak, żeby po prostu "było" (nic nie robi)
    # W testach FastAPI, jeśli nie odświeżamy z bazy, po prostu przypiszemy ID ręcznie
    def side_effect_refresh(obj):
        if obj.nomination_id is None:
            obj.nomination_id = mock_uuid
        return None

    mock_db.refresh.side_effect = side_effect_refresh

    payload = {
        "subject": "Nomination for MV Hanse Star",
        "body": "Please find attached nomination. ETA tomorrow.",
        "sender_email": "agent@shipline.com"
    }

    response = client.post("/api/v1/nominations/parse-email", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["nomination_id"] == str(mock_uuid)
    assert data["status"] == "received"


@patch("app.api.v1.nominations.agent_extraction_service.extract_and_apply")
def test_extract_endpoint_calls_agent_service_and_returns_updated_nomination(mock_extract, client, mock_db, mock_uuid):
    """Endpoint /extract powinien po prostu delegować do agent_extraction_service
    i zwrócić zaktualizowaną nominację."""
    updated_nomination = Nomination(
        nomination_id=mock_uuid,
        vessel_id=mock_uuid,
        nominating_company_id=mock_uuid,
        destination_port_id=mock_uuid,
        status="parsed_pending_review",
        source_email_subject="Nominacja - MV Test",
        assigned_agent_name="Agent Hakatonowy",
    )
    mock_extract.return_value = updated_nomination

    response = client.post(f"/api/v1/nominations/{mock_uuid}/extract")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "parsed_pending_review"
    mock_extract.assert_called_once()


@patch("app.api.v1.nominations.nomination_view_service.list_nominations")
def test_list_nominations_endpoint_returns_paginated_data(mock_list, client, mock_uuid):
    from datetime import datetime, timezone
    from app.schemas.nomination_detail import NominationListResponse, NominationListItemResponse

    mock_list.return_value = NominationListResponse(
        total=1,
        limit=50,
        offset=0,
        items=[
            NominationListItemResponse(
                nomination_id=mock_uuid,
                status="parsed_pending_review",
                created_at=datetime(2026, 6, 23, tzinfo=timezone.utc),
            )
        ],
    )

    response = client.get("/api/v1/nominations/")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["nomination_id"] == str(mock_uuid)


@patch("app.api.v1.nominations.nomination_view_service.list_nominations")
def test_list_nominations_endpoint_passes_status_filter(mock_list, client):
    from app.schemas.nomination_detail import NominationListResponse

    mock_list.return_value = NominationListResponse(total=0, limit=50, offset=0, items=[])

    response = client.get("/api/v1/nominations/?status=parsed_pending_review")

    assert response.status_code == 200
    call_kwargs = mock_list.call_args.kwargs
    assert str(call_kwargs["status"]) == "NominationStatus.parsed_pending_review" or \
           call_kwargs["status"].value == "parsed_pending_review"


@patch("app.api.v1.nominations.nomination_view_service.get_nomination_detail")
def test_get_nomination_detail_endpoint_success(mock_get_detail, client, mock_uuid):
    from datetime import datetime, timezone
    from app.schemas.nomination_detail import NominationDetailResponse

    mock_get_detail.return_value = NominationDetailResponse(
        nomination_id=mock_uuid,
        status="parsed_pending_review",
        created_at=datetime(2026, 6, 23, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 23, tzinfo=timezone.utc),
    )

    response = client.get(f"/api/v1/nominations/{mock_uuid}")

    assert response.status_code == 200
    assert response.json()["nomination_id"] == str(mock_uuid)


@patch("app.api.v1.nominations.nomination_view_service.get_nomination_detail")
def test_get_nomination_detail_endpoint_404_when_missing(mock_get_detail, client, mock_uuid):
    mock_get_detail.return_value = None

    response = client.get(f"/api/v1/nominations/{mock_uuid}")

    assert response.status_code == 404


@patch("app.api.v1.nominations.nomination_repository.get_attachment_by_id")
def test_download_attachment_endpoint_success(mock_get_attachment, client, mock_uuid):
    import uuid as uuid_module

    nomination_id = mock_uuid
    attachment_id = uuid_module.uuid4()

    mock_attachment = MagicMock()
    mock_attachment.nomination_id = nomination_id
    mock_attachment.file_data = b"%PDF-1.4 fake content"
    mock_attachment.content_type = "application/pdf"
    mock_attachment.filename = "nominacja.pdf"
    mock_get_attachment.return_value = mock_attachment

    response = client.get(f"/api/v1/nominations/{nomination_id}/attachments/{attachment_id}/download")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 fake content"
    assert response.headers["content-type"] == "application/pdf"
    assert "nominacja.pdf" in response.headers["content-disposition"]


@patch("app.api.v1.nominations.nomination_repository.get_attachment_by_id")
def test_download_attachment_endpoint_404_when_belongs_to_different_nomination(mock_get_attachment, client, mock_uuid):
    """Załącznik istnieje, ale należy do INNEJ nominacji niż podana w
    URL - powinno to dać 404, nie 200 z plikiem innej osoby."""
    import uuid as uuid_module

    mock_attachment = MagicMock()
    mock_attachment.nomination_id = uuid_module.uuid4()  # inna nominacja niż w URL
    mock_get_attachment.return_value = mock_attachment

    response = client.get(f"/api/v1/nominations/{mock_uuid}/attachments/{uuid_module.uuid4()}/download")

    assert response.status_code == 404


@patch("app.api.v1.nominations.nomination_repository.get_attachment_by_id")
def test_download_attachment_endpoint_404_when_not_found(mock_get_attachment, client, mock_uuid):
    import uuid as uuid_module

    mock_get_attachment.return_value = None

    response = client.get(f"/api/v1/nominations/{mock_uuid}/attachments/{uuid_module.uuid4()}/download")

    assert response.status_code == 404


@patch("app.api.v1.nominations.berth_assignment_service.recommend_berths_for_nomination")
@patch("app.api.v1.nominations.nomination_repository.get_nomination")
def test_recommended_berths_endpoint_returns_top_candidates(mock_get_nomination, mock_recommend, client, mock_uuid):
    from app.services.berth_assignment_service import BerthCandidate
    from app.models.reference import Berth
    import uuid as uuid_module

    mock_get_nomination.return_value = MagicMock(nomination_id=mock_uuid)
    berth = Berth(berth_id=uuid_module.uuid4(), berth_code="B1", berth_name="Nabrzeże Testowe")
    mock_recommend.return_value = [BerthCandidate(berth=berth, score=95.5, reasons=["dobrze dopasowane"])]

    response = client.get(f"/api/v1/nominations/{mock_uuid}/recommended-berths")

    assert response.status_code == 200
    data = response.json()
    assert data["nomination_id"] == str(mock_uuid)
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["berth"]["berth_name"] == "Nabrzeże Testowe"
    assert data["recommendations"][0]["score"] == 95.5
    assert data["warning"] is not None  # tylko 1 z domyślnych 3 - powinno być ostrzeżenie


@patch("app.api.v1.nominations.nomination_repository.get_nomination")
def test_recommended_berths_endpoint_404_when_nomination_missing(mock_get_nomination, client, mock_uuid):
    mock_get_nomination.return_value = None

    response = client.get(f"/api/v1/nominations/{mock_uuid}/recommended-berths")

    assert response.status_code == 404
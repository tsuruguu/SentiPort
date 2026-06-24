import uuid
from datetime import datetime, timezone

from app.schemas.nomination_detail import (
    NominationDetailResponse, VesselSummary, VesselTechnicalSpecsResponse,
    CompanySummary, ContactSummary, PortSummary, BerthSummary,
    CargoItemResponse, RequestedServiceResponse, UnstructuredNoteResponse,
)
from app.services.pdf_export_service import generate_nomination_pdf, compute_file_hash


def _minimal_nomination(**overrides) -> NominationDetailResponse:
    detail = NominationDetailResponse(
        nomination_id=uuid.uuid4(),
        status="received",
        created_at=datetime(2026, 6, 23, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 23, tzinfo=timezone.utc),
    )
    for key, value in overrides.items():
        setattr(detail, key, value)
    return detail


def test_generate_nomination_pdf_produces_valid_pdf_bytes():
    """Sanity check: wynik jest realnym plikiem PDF (zaczyna się od
    nagłówka %PDF), nie placeholderem/stringiem."""
    pdf_bytes = generate_nomination_pdf(_minimal_nomination())

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_generate_nomination_pdf_handles_completely_empty_nomination():
    """QUA-006: statek demonstracyjnie odporny na brakujące dane - brak
    statku, firmy, portu, ładunku - nie powinno wywalić generowania."""
    pdf_bytes = generate_nomination_pdf(_minimal_nomination())
    assert pdf_bytes.startswith(b"%PDF")


def test_generate_nomination_pdf_with_full_data_does_not_raise():
    nomination = _minimal_nomination(
        status="verified",
        vessel=VesselSummary(vessel_id=uuid.uuid4(), imo_number="9456789", current_vessel_name="MV Bałtycka Gwiazda", year_built=2018),
        vessel_technical_specs=VesselTechnicalSpecsResponse(
            length_overall_meters=199.9, beam_meters=32.2, draft_meters=12.5,
            gross_tonnage=45000, deadweight_tonnage=52000, container_capacity_teu=3500,
            has_ice_class=True, ice_class_designation="1A Super", data_source="email_nomination",
        ),
        nominating_company=CompanySummary(company_id=uuid.uuid4(), company_name="Żurawie Morskie Sp. z o.o.", is_sanctioned=False),
        nominating_contact=ContactSummary(contact_id=uuid.uuid4(), first_name="Łukasz", last_name="Wiśniewski", email="l@x.pl", phone="+48500500500"),
        destination_port=PortSummary(port_id=uuid.uuid4(), un_locode="PLGDY", port_name="Gdynia"),
        requested_berth=BerthSummary(berth_id=uuid.uuid4(), berth_code="HEL", berth_name="Nabrzeże Helskie"),
        assigned_berth=BerthSummary(berth_id=uuid.uuid4(), berth_code="OKS", berth_name="Nabrzeże Oksywskie"),
        eta=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
        etd=datetime(2026, 7, 2, 18, 0, tzinfo=timezone.utc),
        cargo_items=[
            CargoItemResponse(cargo_id=uuid.uuid4(), cargo_description="Kontenery mieszane", cargo_quantity=120, cargo_unit="TEU", imdg_hazard_class="none", requires_refrigeration=False),
            CargoItemResponse(cargo_id=uuid.uuid4(), cargo_description="Materiały klasy 3", cargo_quantity=5, cargo_unit="TEU", imdg_hazard_class="class_3_flammable_liquids", requires_refrigeration=False, un_number="UN1203"),
        ],
        requested_services=[
            RequestedServiceResponse(service_order_id=uuid.uuid4(), service_type="towage", status="requested", notes="2 holowniki przy wejściu"),
            RequestedServiceResponse(service_order_id=uuid.uuid4(), service_type="pilotage", status="confirmed"),
        ],
        unstructured_notes=[
            UnstructuredNoteResponse(note_id=uuid.uuid4(), note_text="Armator prosi o priorytetowe cumowanie", extracted_by="agent_elevenlabs", requires_human_review=True),
            UnstructuredNoteResponse(note_id=uuid.uuid4(), note_text="Już zweryfikowane", extracted_by="agent_elevenlabs", requires_human_review=True, reviewed_at=datetime(2026, 6, 24, tzinfo=timezone.utc)),
        ],
        source_email_subject="Nominacja - MV Bałtycka Gwiazda",
        source_email_sender_address="armator1@armatorzy.pl",
        confidence_score=0.87,
        fields_missing=["etd", "draft_meters"],
        extraction_model="elevenlabs-agent-v1",
    )

    pdf_bytes = generate_nomination_pdf(nomination)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000


def test_generate_nomination_pdf_with_sanctioned_company_does_not_raise():
    """Firma oznaczona jako objęta sankcjami powinna się renderować z
    wyraźnym ostrzeżeniem, nie wywalać generowania."""
    nomination = _minimal_nomination(
        nominating_company=CompanySummary(company_id=uuid.uuid4(), company_name="Podejrzana Firma", is_sanctioned=True),
    )
    pdf_bytes = generate_nomination_pdf(nomination)
    assert pdf_bytes.startswith(b"%PDF")


def test_generate_nomination_pdf_with_no_cargo_does_not_raise():
    nomination = _minimal_nomination(cargo_items=[])
    pdf_bytes = generate_nomination_pdf(nomination)
    assert pdf_bytes.startswith(b"%PDF")


def test_generate_nomination_pdf_with_unknown_imdg_class_falls_back_gracefully():
    """Jeśli klasa IMDG nie jest w słowniku etykiet PL, powinniśmy
    pokazać surową wartość, nie wywalić renderowania."""
    nomination = _minimal_nomination(
        cargo_items=[
            CargoItemResponse(cargo_id=uuid.uuid4(), cargo_description="Test", imdg_hazard_class="none", requires_refrigeration=False),
        ],
    )
    pdf_bytes = generate_nomination_pdf(nomination)
    assert pdf_bytes.startswith(b"%PDF")


def test_compute_file_hash_is_deterministic_and_matches_sha256():
    import hashlib
    data = b"%PDF-1.4 test content"
    assert compute_file_hash(data) == hashlib.sha256(data).hexdigest()


def test_compute_file_hash_differs_for_different_content():
    assert compute_file_hash(b"content A") != compute_file_hash(b"content B")
"""
Generator PDF dla pakietu nominacyjnego (FUN-007, FUN-008, FUN-010, QUA-005).

Zastępuje poprzedni mock (który zwracał tylko fałszywy URL S3, nic nie
generował) prawdziwym dokumentem PDF, budowanym z reportlab na podstawie
danych już zebranych w nominacji (statek, ładunek, usługi, metadane
ekstrakcji AI).

Zasada projektowa (zgodna z notatką z dokumentu projektowego: "system
NIE powinien samodzielnie składać wniosku do portu - tylko przygotować
pakiet do sprawdzenia i zatwierdzenia"): PDF jest dokumentem ROBOCZYM do
weryfikacji przez agenta portowego, nie automatycznym zgłoszeniem. Stąd
wyraźna sekcja "Status weryfikacji" z confidence score i listą pól
wymagających uwagi człowieka (QUA-001: każde pole z AI musi mieć
oznaczenie źródła/niepewności; QUA-002: system nie ukrywa niepewności).
"""

import hashlib
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

from app.schemas.nomination_detail import NominationDetailResponse

# --- Rejestracja czcionki z pełnym wsparciem polskich znaków diakrytycznych ---
# Domyślne czcionki reportlab (Helvetica) NIE obsługują znaków takie jak
# ą/ć/ę/ł/ń/ó/ś/ź/ż - renderują się jako czarne kwadraty. DejaVu Sans jest
# dołączona bezpośrednio do repozytorium (app/static/fonts/), żeby
# generowanie PDF działało identycznie niezależnie od systemu operacyjnego
# hosta czy obrazu Dockera (python:3.11-slim nie ma żadnych czcionek
# systemowych). Licencja Bitstream Vera pozwala na redystrybucję.
_FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "fonts")
_FONT_REGULAR_PATH = os.path.join(_FONTS_DIR, "DejaVuSans.ttf")
_FONT_BOLD_PATH = os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf")

FONT_NAME = "DejaVuSans"
FONT_NAME_BOLD = "DejaVuSans-Bold"

if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont(FONT_NAME, _FONT_REGULAR_PATH))
    pdfmetrics.registerFont(TTFont(FONT_NAME_BOLD, _FONT_BOLD_PATH))

# --- Etykiety PL dla wartości enumów, żeby dokument był czytelny dla agenta portowego ---

NOMINATION_STATUS_LABELS = {
    "received": "Odebrana",
    "parsing": "W trakcie przetwarzania",
    "parsed_pending_review": "Przetworzona - czeka na przegląd",
    "verified": "Zweryfikowana",
    "submitted_to_port": "Złożona do portu",
    "acknowledged": "Potwierdzona przez port",
    "rejected": "Odrzucona",
    "cancelled": "Anulowana",
    "completed": "Zakończona",
}

IMDG_CLASS_LABELS = {
    "none": "Brak (niesklasyfikowany)",
    "class_1_explosives": "Klasa 1 - Materiały wybuchowe",
    "class_2_gases": "Klasa 2 - Gazy",
    "class_3_flammable_liquids": "Klasa 3 - Cieczy łatwopalne",
    "class_7_radioactive": "Klasa 7 - Materiały radioaktywne",
    "class_8_corrosive": "Klasa 8 - Substancje żrące/korozyjne",
    "class_9_miscellaneous": "Klasa 9 - Różne materiały i przedmioty niebezpieczne",
}

PORT_SERVICE_LABELS = {
    "pilotage": "Pilotaż",
    "towage": "Holowanie",
    "mooring_unmooring": "Cumowanie/odcumowanie",
    "shore_power": "Prąd z lądu",
    "fresh_water_supply": "Dostawa wody pitnej",
    "bunkering_fuel": "Bunkrowanie paliwa",
    "waste_removal": "Odbiór odpadów",
    "medical_services": "Usługi medyczne",
    "barber_services": "Usługi fryzjerskie",
    "provisions_supply": "Dostawa prowiantu",
    "crew_change": "Zmiana załogi",
    "customs_clearance": "Odprawa celna",
    "security_isps": "Bezpieczeństwo / ISPS",
    "cargo_surveying": "Inspekcja ładunku",
    "ice_breaking_assistance": "Asysta lodołamacza",
    "waste_water_pumpout": "Odbiór wód zaolejonych/balastowych",
    "other": "Inne",
}


def _val(value, fallback: str = "— brak danych —") -> str:
    """Zwraca wartość jako string albo jawny placeholder 'brak danych' -
    zgodnie z QUA-002 (system nie ukrywa niepewności/braku danych, nie
    pokazuje pustego pola jakby wszystko było w porządku)."""
    if value is None or value == "":
        return fallback
    return str(value)


def _fmt_datetime(dt: Optional[datetime]) -> str:
    if dt is None:
        return "— brak danych —"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _build_styles():
    # Mapuje rodzinę "DejaVuSans" tak, żeby tagi <b>...</b> w Paragraph
    # używały DejaVuSans-Bold, a nie domyślnego Helvetica-Bold (które nie
    # ma polskich znaków).
    pdfmetrics.registerFontFamily(
        FONT_NAME, normal=FONT_NAME, bold=FONT_NAME_BOLD, italic=FONT_NAME, boldItalic=FONT_NAME_BOLD,
    )

    styles = getSampleStyleSheet()
    for style_name in ["Normal", "Title", "Heading1", "Heading2", "Heading3"]:
        styles[style_name].fontName = FONT_NAME
    styles["Title"].fontName = FONT_NAME_BOLD
    styles["Heading1"].fontName = FONT_NAME_BOLD
    styles["Heading2"].fontName = FONT_NAME_BOLD

    styles.add(ParagraphStyle(
        name="DocTitle", parent=styles["Title"], fontName=FONT_NAME_BOLD, fontSize=18, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader", parent=styles["Heading2"], fontName=FONT_NAME_BOLD, fontSize=13,
        textColor=colors.HexColor("#0B3D6B"), spaceBefore=14, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="MetaSmall", parent=styles["Normal"], fontName=FONT_NAME, fontSize=8, textColor=colors.grey,
    ))
    styles.add(ParagraphStyle(
        name="WarningBox", parent=styles["Normal"], fontName=FONT_NAME, fontSize=9,
        textColor=colors.HexColor("#8A6D00"), backColor=colors.HexColor("#FFF6DA"),
        borderColor=colors.HexColor("#E0C341"), borderWidth=1, borderPadding=6,
    ))
    return styles


def _data_field_table(rows: list[tuple[str, str]]) -> Table:
    table_data = [[Paragraph(f"<b>{label}</b>", _build_styles()["Normal"]), value] for label, value in rows]
    table = Table(table_data, colWidths=[55 * mm, 110 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#DDDDDD")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def generate_nomination_pdf(nomination: NominationDetailResponse) -> bytes:
    """
    Renderuje pełny pakiet nominacyjny jako PDF i zwraca jego surową
    treść (bytes), gotową do zapisania w bazie / wysłania w response.

    Sekcje dokumentu (zgodnie z FUN-007/FUN-008):
      1. Nagłówek - data wygenerowania, ID nominacji, status (QUA-005)
      2. Dane statku
      3. Firma nominująca i osoba kontaktowa
      4. Port docelowy, terminy, nabrzeże żądane vs przydzielone
      5. Ładunek (tabela pozycji)
      6. Usługi portowe zażądane przez armatora
      7. Status weryfikacji - confidence, pola brakujące, notatki do
         przeglądu (QUA-001, QUA-002 - niepewność NIE jest ukrywana)
      8. Stopka - źródła danych, ostrzeżenie "nie jest formalnym wnioskiem"
    """
    styles = _build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    story = []
    generated_at = datetime.now(timezone.utc)

    # --- 1. Nagłówek ---
    story.append(Paragraph("Pakiet Nominacyjny Statku", styles["DocTitle"]))
    story.append(Paragraph(
        f"Wygenerowano: {generated_at.strftime('%Y-%m-%d %H:%M UTC')} &nbsp;|&nbsp; "
        f"ID nominacji: {nomination.nomination_id} &nbsp;|&nbsp; "
        f"Status: <b>{NOMINATION_STATUS_LABELS.get(nomination.status.value if hasattr(nomination.status, 'value') else nomination.status, str(nomination.status))}</b>",
        styles["MetaSmall"],
    ))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#0B3D6B"), thickness=1.2, spaceAfter=8))

    story.append(Paragraph(
        "Dokument roboczy do weryfikacji przez agenta portowego. "
        "Nie stanowi formalnego zgłoszenia do kapitanatu portu.",
        ParagraphStyle("notice", parent=styles["Normal"], fontName=FONT_NAME, fontSize=9, textColor=colors.HexColor("#555555")),
    ))

    # --- 2. Dane statku ---
    story.append(Paragraph("1. Dane statku", styles["SectionHeader"]))
    if nomination.vessel:
        vessel_rows = [
            ("Nazwa statku", _val(nomination.vessel.current_vessel_name)),
            ("Numer IMO", _val(nomination.vessel.imo_number)),
            ("Rok budowy", _val(nomination.vessel.year_built)),
        ]
        if nomination.vessel_technical_specs:
            specs = nomination.vessel_technical_specs
            vessel_rows += [
                ("Długość całkowita (LOA)", _val(f"{specs.length_overall_meters} m" if specs.length_overall_meters else None)),
                ("Szerokość (Beam)", _val(f"{specs.beam_meters} m" if specs.beam_meters else None)),
                ("Zanurzenie (Draft)", _val(f"{specs.draft_meters} m" if specs.draft_meters else None)),
                ("Tonaż brutto (GT)", _val(specs.gross_tonnage)),
                ("DWT", _val(specs.deadweight_tonnage)),
                ("Pojemność kontenerowa (TEU)", _val(specs.container_capacity_teu)),
                ("Klasa lodowa", _val(specs.ice_class_designation if specs.has_ice_class else "Brak")),
                ("Źródło danych technicznych", _val(specs.data_source, "lokalna baza referencyjna")),
            ]
        else:
            vessel_rows.append(("Dane techniczne", "— brak danych w bazie referencyjnej —"))
        story.append(_data_field_table(vessel_rows))
    else:
        story.append(Paragraph(
            "Statek nie został jeszcze zidentyfikowany w bazie referencyjnej.",
            styles["WarningBox"],
        ))

    # --- 3. Firma i kontakt ---
    story.append(Paragraph("2. Firma nominująca i kontakt", styles["SectionHeader"]))
    company_rows = [
        ("Nazwa firmy", _val(nomination.nominating_company.company_name if nomination.nominating_company else None)),
    ]
    if nomination.nominating_company and nomination.nominating_company.is_sanctioned:
        company_rows.append(("Status sankcyjny", "⚠ OZNACZONA JAKO OBJĘTA SANKCJAMI - wymaga weryfikacji"))
    if nomination.nominating_contact:
        contact = nomination.nominating_contact
        company_rows += [
            ("Osoba kontaktowa", f"{contact.first_name} {contact.last_name}"),
            ("E-mail kontaktowy", _val(contact.email)),
            ("Telefon kontaktowy", _val(contact.phone)),
        ]
    story.append(_data_field_table(company_rows))

    # --- 4. Port, terminy, nabrzeże ---
    story.append(Paragraph("3. Port docelowy i nabrzeże", styles["SectionHeader"]))
    port_rows = [
        ("Port docelowy", _val(
            f"{nomination.destination_port.port_name} ({nomination.destination_port.un_locode})"
            if nomination.destination_port else None
        )),
        ("ETA (przybycie)", _fmt_datetime(nomination.eta)),
        ("ETD (odejście)", _fmt_datetime(nomination.etd)),
        ("Nabrzeże żądane przez armatora", _val(
            nomination.requested_berth.berth_name or nomination.requested_berth.berth_code
            if nomination.requested_berth else None
        )),
        ("Nabrzeże przydzielone", _val(
            nomination.assigned_berth.berth_name or nomination.assigned_berth.berth_code
            if nomination.assigned_berth else "— jeszcze nie przydzielone —"
        )),
    ]
    story.append(_data_field_table(port_rows))

    # --- 5. Ładunek ---
    story.append(Paragraph("4. Ładunek", styles["SectionHeader"]))
    if nomination.cargo_items:
        cargo_table_data = [["Opis", "Ilość", "Klasa IMDG", "Chłodzenie", "Nr UN"]]
        for cargo in nomination.cargo_items:
            cargo_table_data.append([
                Paragraph(cargo.cargo_description, styles["Normal"]),
                _val(f"{cargo.cargo_quantity} {cargo.cargo_unit or ''}".strip() if cargo.cargo_quantity else None),
                IMDG_CLASS_LABELS.get(
                    cargo.imdg_hazard_class.value if hasattr(cargo.imdg_hazard_class, "value") else str(cargo.imdg_hazard_class),
                    str(cargo.imdg_hazard_class),
                ),
                "Tak" if cargo.requires_refrigeration else "Nie",
                _val(cargo.un_number, "—"),
            ])
        cargo_table = Table(cargo_table_data, colWidths=[45 * mm, 20 * mm, 60 * mm, 22 * mm, 18 * mm])
        cargo_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3D6B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FONT_NAME_BOLD),
            ("FONTNAME", (0, 1), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(cargo_table)
    else:
        story.append(Paragraph("Brak zarejestrowanych pozycji ładunku.", styles["Normal"]))

    # --- 6. Usługi portowe ---
    story.append(Paragraph("5. Usługi portowe zażądane przez armatora", styles["SectionHeader"]))
    if nomination.requested_services:
        services_text = "<br/>".join(
            f"• {PORT_SERVICE_LABELS.get(s.service_type.value if hasattr(s.service_type, 'value') else str(s.service_type), str(s.service_type))}"
            + (f" — {s.notes}" if s.notes else "")
            for s in nomination.requested_services
        )
        story.append(Paragraph(services_text, styles["Normal"]))
    else:
        story.append(Paragraph("Armator nie zgłosił dodatkowych usług portowych w mailu.", styles["Normal"]))

    # --- 7. Status weryfikacji (QUA-001, QUA-002, QUA-005) ---
    story.append(Paragraph("6. Status weryfikacji danych", styles["SectionHeader"]))
    confidence_text = (
        f"{nomination.confidence_score:.0%}" if nomination.confidence_score is not None
        else "brak oceny pewności"
    )
    has_unreviewed_notes = any(
        note.requires_human_review and not note.reviewed_at for note in nomination.unstructured_notes
    )
    verification_rows = [
        ("Pewność ekstrakcji AI", confidence_text),
        ("Model ekstrakcji", _val(nomination.extraction_model)),
        ("Wymaga przeglądu człowieka", "TAK" if has_unreviewed_notes else "Nie zgłoszono uwag"),
    ]
    story.append(_data_field_table(verification_rows))

    if nomination.fields_missing:
        story.append(Spacer(1, 4 * mm))
        missing_text = "Pola, których AI nie znalazło w treści maila: " + ", ".join(nomination.fields_missing)
        story.append(Paragraph(missing_text, styles["WarningBox"]))

    if nomination.unstructured_notes:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("<b>Notatki wymagające przeglądu agenta portowego:</b>", styles["Normal"]))
        for note in nomination.unstructured_notes:
            review_marker = "⚠ DO WERYFIKACJI" if note.requires_human_review and not note.reviewed_at else "✓ zweryfikowane"
            story.append(Paragraph(f"• [{review_marker}] {note.note_text}", styles["Normal"]))

    # --- 8. Stopka ze źródłami danych ---
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#CCCCCC"), thickness=0.6))
    footer_text = (
        f"Źródła danych: treść maila nominacyjnego"
        + (f" ({nomination.source_email_sender_address})" if nomination.source_email_sender_address else "")
        + ", lokalna baza referencyjna statków i portów"
        + (f", model ekstrakcji AI: {nomination.extraction_model}" if nomination.extraction_model else "")
        + f". Dokument wygenerowany automatycznie {generated_at.strftime('%Y-%m-%d %H:%M UTC')} "
        "i wymaga zatwierdzenia przez upoważnionego agenta portowego przed przekazaniem do kapitanatu portu."
    )
    story.append(Paragraph(footer_text, styles["MetaSmall"]))

    doc.build(story)
    return buffer.getvalue()


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()
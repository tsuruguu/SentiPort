import logging
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.models.operations import Nomination, NominationUnstructuredNote, CargoManifest
from app.models.enums import NominationStatus, ImdgHazardClass
from app.models.vessel import Vessel
from app.models.company import Company
from app.models.reference import Port, Berth

logger = logging.getLogger(__name__)


def seed_additional_nominations(db: Session, count: int = 50):
    """
    Generuje potężną paczkę (np. 50 sztuk) realistycznych danych operacyjnych.
    Zapewni to piękny, "żywy" dashboard podczas prezentacji dla jury.
    """
    # 1. Pobieramy pule zasobów z bazy
    vessels = db.query(Vessel).all()
    companies = db.query(Company).all()
    ports = db.query(Port).all()
    berths = db.query(Berth).all()

    if not vessels or not companies or not ports:
        logger.warning("Brak danych słownikowych w bazie. Odpal wpierw: python scripts/run_seed.py")
        return

    # Zabezpieczenie przed dublowaniem przy wielokrotnym odpaleniu
    existing_count = db.query(Nomination).filter(Nomination.assigned_agent_name == "Michał Samaruk").count()
    if existing_count >= count:
        logger.info(f"W bazie jest już wystarczająco nominacji ({existing_count}). Pomijam seedowanie ORM.")
        return

    now_utc = datetime.now(timezone.utc)

    # Listy pomocnicze
    subjects = [
        "Vessel Nomination", "Notice of Readiness", "Port Call Request",
        "ETA Update", "Urgent: Berth requirement", "Agency Appointment"
    ]
    notes = [
        "Armator prosi o asystę lodołamacza jeśli warunki się pogorszą.",
        "Uwaga: Na pokładzie zmiana załogi (3 oficerów). Wymagany transport.",
        "Wymagane dodatkowe przyłącza chłodnicze na nabrzeżu.",
        "Kapitan zgłasza drobne problemy z silnikiem głównym, prosi o kontakt z serwisem.",
        "Ładunek wrażliwy na wilgoć, prośba o priorytetowy rozładunek.",
        "Potrzebny pilny kontakt z lekarzem portowym (drobny uraz członka załogi).",
        "Wymagane bunkrowanie (MGO 150 MT) zaraz po zacumowaniu.",
        "Agent poproszony o zorganizowanie transportu dla inspektora klasy."
    ]

    logger.info(f"🚀 Generowanie {count} potężnych nominacji dla Agenta...")

    for i in range(count):
        vessel = random.choice(vessels)
        company = random.choice(companies)
        port = random.choice(ports)
        berth = random.choice(berths) if random.random() > 0.3 else None

        # Statusy
        status_weights = [
            (NominationStatus.completed, 0.40),
            (NominationStatus.parsed_pending_review, 0.20),
            (NominationStatus.received, 0.10),
            (NominationStatus.verified, 0.15),
            (NominationStatus.submitted_to_port, 0.10),
            (NominationStatus.rejected, 0.05)
        ]
        status = random.choices([s[0] for s in status_weights], weights=[s[1] for s in status_weights], k=1)[0]

        # Daty
        eta_days = random.randint(-30, -2) if status == NominationStatus.completed else random.randint(-1, 14)
        eta = now_utc + timedelta(days=eta_days, hours=random.randint(0, 23))
        etd = eta + timedelta(days=random.randint(1, 4), hours=random.randint(0, 12))

        # Rekord Nominacji
        nomination = Nomination(
            vessel_id=vessel.vessel_id,
            nominating_company_id=company.company_id,
            destination_port_id=port.port_id,
            status=status,
            eta=eta,
            etd=etd,
            assigned_berth_id=berth.berth_id if berth else None,
            source_email_subject=f"{random.choice(subjects)} - {vessel.current_vessel_name}",
            source_email_body_raw=f"Automatycznie wygenerowany mail. Statek: {vessel.current_vessel_name}, IMO: {vessel.imo_number}.",
            assigned_agent_name="Michał Samaruk",
            llm_extraction_metadata={
                "confidence_score": round(random.uniform(0.75, 0.99), 2),
                "model": "gpt-4o-mini"
            }
        )
        db.add(nomination)
        db.flush()

        # Ładunek z dynamicznie generowanymi wagami (TO JEST KLUCZ DO NAPRAWY BŁĘDU)
        imdg_classes = list(ImdgHazardClass)
        # Tworzymy wagi o dokładnie takiej samej długości jak lista klas
        dynamic_weights = [1.0 / len(imdg_classes) for _ in imdg_classes]

        cargo = CargoManifest(
            nomination_id=nomination.nomination_id,
            cargo_description=f"Partia towaru dla {vessel.current_vessel_name}",
            cargo_quantity=random.randint(100, 50000),
            cargo_unit=random.choice(["tonnes", "TEU", "CBM"]),
            imdg_hazard_class=random.choices(imdg_classes, weights=dynamic_weights, k=1)[0],
            requires_refrigeration=(random.random() > 0.8),
            is_perishable=(random.random() > 0.85)
        )
        db.add(cargo)

        # Notatka
        if random.random() > 0.5:
            note = NominationUnstructuredNote(
                nomination_id=nomination.nomination_id,
                note_text=random.choice(notes),
                extracted_by="llm",
                confidence_score=round(random.uniform(0.60, 0.95), 2),
                requires_human_review=True
            )
            db.add(note)

    try:
        db.commit()
        logger.info(f"✅ Sukces! Wygenerowano {count} nominacji.")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Błąd podczas seedowania: {e}")
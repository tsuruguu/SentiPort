import pandas as pd
from sqlalchemy.orm import Session
from app.models.operations import Nomination
from app.models.vessel import Vessel
from app.models.company import Company
from app.models.reference import Port
from app.database import SessionLocal
import logging


def import_emails_from_csv(file_path: str):
    df = pd.read_csv(file_path, sep=';')
    db = SessionLocal()

    vessel = db.query(Vessel).first()
    company = db.query(Company).first()
    port = db.query(Port).first()

    if not all([vessel, company, port]):
        print("Błąd: Brak danych w bazie. Uruchom run_seed.py!")
        return

    print(f"Importowanie {len(df)} maili do bazy...")

    for _, row in df.iterrows():
        nomination = Nomination(
            vessel_id=vessel.vessel_id,
            nominating_company_id=company.company_id,
            destination_port_id=port.port_id,
            source_email_subject=row['subject'],
            source_email_body_raw=row['body'],
            status='received',
            assigned_agent_name="Michał Samaruk"
        )
        db.add(nomination)

    db.commit()
    print("Import zakończony!")


if __name__ == "__main__":
    import_emails_from_csv("seed/data/syntetyczne_maile_awizacje_statkow_75.csv")
# backend/scripts/init_db.py
import sys
import os

# Dodajemy katalog nadrzędny do sys.path, aby importy z 'app' i 'seed' działały
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seed.seed_data import seed_additional_nominations
from seed.seed_csv_importer import import_emails_from_csv
from app.database import SessionLocal


def run_all_seeds():
    print("🧹 Inicjalizacja bazy danych...")
    db = SessionLocal()

    try:
        # 1. Seedowanie podstawowej struktury (statki, firmy, porty)
        # Zakładam, że Twoja funkcja seed_additional_nominations przyjmuje 'db'
        print("🚢 Seedowanie statków i firm...")
        seed_additional_nominations(db, count=50)

        # 2. Import 75 maili z CSV
        # Upewnij się, że ścieżka jest poprawna względem katalogu 'backend'
        csv_path = "seed/data/syntetyczne_maile_awizacje_statkow_75.csv"
        print(f"📧 Importowanie {csv_path}...")
        import_emails_from_csv(csv_path)

        db.commit()
        print("✨ Gotowe! Baza jest pełna danych.")

    except Exception as e:
        db.rollback()
        print(f"❌ Wystąpił błąd podczas seedowania: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    run_all_seeds()
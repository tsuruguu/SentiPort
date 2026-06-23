import os
import logging
import sys

# Dodajemy folder wyżej do ścieżki, żeby Python widział nasz pakiet 'app'
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_seed():
    # Szukamy pliku baza.sql o jeden katalog wyżej (czyli w backend/)
    sql_file_path = os.path.join(os.path.dirname(__file__), "..", "baza.sql")

    if not os.path.exists(sql_file_path):
        logger.error(f"❌ Nie znaleziono pliku {sql_file_path}! Upewnij się, że baza.sql leży w folderze backend/.")
        sys.exit(1)

    engine = create_engine(settings.DATABASE_URL)

    logger.info(f"Wczytywanie pliku SQL: {sql_file_path}")
    with open(sql_file_path, "r", encoding="utf-8") as f:
        sql_commands = f.read()

    logger.info("Wykonywanie skryptu SQL (to może zająć kilka-kilkanaście sekund)...")

    try:
        # Używamy surowego kursora psycopg2, by bez problemu odpalić jeden gigantyczny skrypt
        with engine.raw_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql_commands)
            conn.commit()
        logger.info("🎉 SUKCES! Baza danych została pomyślnie zainicjowana schematem i zasiliona danymi (seed).")
    except Exception as e:
        logger.error(f"❌ Błąd podczas ładowania seeda do bazy. Szczegóły: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_seed()
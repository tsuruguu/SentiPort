import time
import logging
import sys
import os

# Dodajemy folder wyżej do ścieżki, żeby Python widział nasz pakiet 'app'
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def wait_for_db():
    engine = create_engine(settings.DATABASE_URL)
    max_retries = 30
    retries = 0

    while retries < max_retries:
        try:
            # Próbujemy otworzyć połączenie
            with engine.connect() as conn:
                logger.info("✅ Baza danych jest gotowa do pracy!")
                return
        except OperationalError:
            retries += 1
            logger.warning(f"Baza danych jeszcze wstaje... Próba {retries}/{max_retries}. Czekam 2 sekundy.")
            time.sleep(2)

    logger.error("❌ Baza danych nie odpowiedziała w wyznaczonym czasie!")
    sys.exit(1)


if __name__ == "__main__":
    logger.info("Oczekiwanie na bazę danych PostgreSQL...")
    wait_for_db()
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Inicjalizacja silnika bazy danych
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Automatycznie sprawdza, czy połączenie żyje
)

# Fabryka sesji
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency injection dla FastAPI - daje nam sesję DB do każdego requestu
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
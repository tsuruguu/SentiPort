from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Tworzymy silnik bazy danych (pool_pre_ping chroni przed zerwaniem połączenia)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

# Fabryka sesji
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
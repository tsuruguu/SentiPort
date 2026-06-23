from sqlalchemy.orm import Session
from app.models.reference import Country


def get_country_by_iso_alpha2(db: Session, iso_alpha2: str) -> Country | None:
    if not iso_alpha2:
        return None
    return db.query(Country).filter(Country.iso_alpha2 == iso_alpha2.upper()).first()
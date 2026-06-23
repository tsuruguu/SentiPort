from sqlalchemy.orm import Session
from app.models.reference import Country
import uuid


def get_country_by_id(db: Session, country_id: int) -> Country | None:
    if not country_id:
        return None
    return db.query(Country).filter(Country.country_id == country_id).first()


def get_country_by_iso_alpha2(db: Session, iso_alpha2: str) -> Country | None:
    if not iso_alpha2:
        return None
    return db.query(Country).filter(Country.iso_alpha2 == iso_alpha2.upper()).first()
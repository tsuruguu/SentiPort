from sqlalchemy.orm import Session
from app.models.company import Company, CompanyContact
import uuid


def get_company_by_id(db: Session, company_id: uuid.UUID) -> Company | None:
    return db.query(Company).filter(Company.company_id == company_id).first()


def get_company_by_imo_number(db: Session, imo_company_number: str) -> Company | None:
    return db.query(Company).filter(Company.imo_company_number == imo_company_number).first()


def get_company_by_name(db: Session, company_name: str) -> Company | None:
    """
    Szuka firmy po nazwie (dopasowanie częściowe, bez rozróżniania
    wielkości liter) - przydatne, gdy agent wyciągnął nazwę z treści
    maila, a w bazie firma jest zapisana z drobnymi różnicami
    (np. 'Sp. z o.o.' vs 'sp. z o.o.').
    """
    if not company_name:
        return None
    return db.query(Company).filter(Company.company_name.ilike(f"%{company_name}%")).first()


def get_contact_by_email(db: Session, email: str) -> CompanyContact | None:
    if not email:
        return None
    return db.query(CompanyContact).filter(CompanyContact.email.ilike(email)).first()


def get_contact_by_name(db: Session, company_id: uuid.UUID, first_name: str, last_name: str) -> CompanyContact | None:
    if not first_name or not last_name:
        return None
    return db.query(CompanyContact).filter(
        CompanyContact.company_id == company_id,
        CompanyContact.first_name.ilike(first_name),
        CompanyContact.last_name.ilike(last_name),
    ).first()
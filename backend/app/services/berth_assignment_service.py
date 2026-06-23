from sqlalchemy.orm import Session
import uuid
from app.repositories import port_repository
from app.models.reference import Berth


def recommend_best_berth(db: Session, port_id: uuid.UUID, requires_reefer: bool, is_dangerous: bool) -> Berth | None:
    """
    Znajduje najlepsze nabrzeże w podanym porcie w zależności od wymagań ładunku.
    """
    berths = port_repository.get_berths_by_port(db, port_id)
    if not berths:
        return None

    # Sortujemy/filtrujemy nabrzeża w pamięci
    best_match = None

    for berth in berths:
        # Jeśli ładunek wymaga chłodni, a nabrzeże tego nie ma -> pomijamy
        if requires_reefer and not berth.supports_reefer_containers:
            continue

        # Jeśli to ładunek niebezpieczny (IMDG), a nabrzeże nie obsługuje -> pomijamy
        if is_dangerous and not berth.supports_dangerous_goods:
            continue

        best_match = berth
        break  # Bierzemy pierwsze pasujące na potrzeby MVP

    # Fallback: jeśli nie znaleźliśmy idealnego, rzucamy jakiekolwiek wolne
    if not best_match and berths:
        best_match = berths[0]

    return best_match
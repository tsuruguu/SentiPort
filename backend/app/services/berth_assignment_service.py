from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from app.repositories import port_repository
from app.models.reference import Berth
from app.models.operations import Nomination, CargoManifest
from app.models.vessel import VesselTechnicalSpecs


def recommend_best_berth(db: Session, port_id: uuid.UUID, requires_reefer: bool, is_dangerous: bool) -> Berth | None:
    """
    Znajduje najlepsze nabrzeże w podanym porcie w zależności od wymagań ładunku.

    UWAGA: to jest uproszczona, pierwotna wersja (MVP) - nie uwzględnia
    wymiarów statku ani kolizji czasowych. Zachowana dla kompatybilności
    z istniejącym kodem/testami. Do nowych miejsc używaj
    recommend_top_berths(), który robi to porządnie (filtr bezpieczeństwa
    + scoring + TOP-3).
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


# ---------------------------------------------------------------------------
# Pełny algorytm: filtr bezpieczeństwa (wykluczenie) + scoring (ranking)
# ---------------------------------------------------------------------------

class BerthCandidate:
    """Wynik oceny jednego nabrzeża - nabrzeże + jego wynik (score) + powody."""
    def __init__(self, berth: Berth, score: float, reasons: List[str]):
        self.berth = berth
        self.score = score
        self.reasons = reasons


def _vessel_requirements(cargo_items: List[CargoManifest]) -> dict:
    """Wyciąga z listy ładunków wymagania bezpieczeństwa dla nabrzeża -
    jeśli JAKIKOLWIEK ładunek wymaga reefera/obsługi towarów niebezpiecznych,
    nabrzeże musi to wspierać (statek wozi WSZYSTKIE swoje ładunki razem)."""
    return {
        "requires_reefer": any(c.requires_refrigeration for c in cargo_items),
        "requires_dangerous_goods": any(
            c.imdg_hazard_class is not None and str(c.imdg_hazard_class.value if hasattr(c.imdg_hazard_class, "value") else c.imdg_hazard_class) != "none"
            for c in cargo_items
        ),
    }


def _passes_safety_filter(
        berth: Berth,
        specs: Optional[VesselTechnicalSpecs],
        requires_reefer: bool,
        requires_dangerous_goods: bool,
        db: Session,
        eta: Optional[datetime],
        etd: Optional[datetime],
) -> Optional[str]:
    """
    Sprawdza BEZWZGLĘDNE wymogi bezpieczeństwa. Zwraca None jeśli
    nabrzeże PRZECHODZI filtr, albo string z powodem odrzucenia jeśli NIE
    przechodzi - takie nabrzeże jest CAŁKOWICIE wykluczone z TOP-3,
    niezależnie od tego, ile innych kandydatów zostanie.
    """
    if not berth.is_active:
        return "nabrzeże nieaktywne"

    if requires_reefer and not berth.supports_reefer_containers:
        return "brak obsługi kontenerów reefer, a ładunek tego wymaga"

    if requires_dangerous_goods and not berth.supports_dangerous_goods:
        return "brak obsługi towarów niebezpiecznych, a ładunek tego wymaga"

    # Wymiary statku - tylko jeśli mamy dane (brak danych nie blokuje,
    # bo armator nie zawsze podaje wymiary w mailu)
    if specs:
        if specs.draft_meters is not None and berth.max_draft_meters is not None:
            if float(specs.draft_meters) > float(berth.max_draft_meters):
                return f"zanurzenie statku ({specs.draft_meters}m) przekracza max nabrzeża ({berth.max_draft_meters}m)"

        if specs.length_overall_meters is not None and berth.max_loa_meters is not None:
            if float(specs.length_overall_meters) > float(berth.max_loa_meters):
                return f"LOA statku ({specs.length_overall_meters}m) przekracza max nabrzeża ({berth.max_loa_meters}m)"

        if specs.deadweight_tonnage is not None and berth.max_dwt_tonnes is not None:
            if float(specs.deadweight_tonnage) > float(berth.max_dwt_tonnes):
                return f"DWT statku ({specs.deadweight_tonnage}t) przekracza max nabrzeża ({berth.max_dwt_tonnes}t)"

    # Kolizja czasowa - tylko jeśli mamy oba terminy (bez nich nie da się
    # ocenić okna czasowego, więc nie blokujemy na ślepo)
    if eta and etd:
        if port_repository.is_berth_occupied_during(db, berth.berth_id, eta, etd):
            return "nabrzeże zajęte w wymaganym oknie czasowym (ETA-ETD)"

    return None


def _score_berth(berth: Berth, specs: Optional[VesselTechnicalSpecs]) -> tuple[float, List[str]]:
    """
    Scoring OPTYMALNOŚCI (nie bezpieczeństwa - to już przeszło filtr).
    Wyższy wynik = lepszy dobór. Preferujemy nabrzeża, których wymiary są
    bliskie wymiarom statku (mniej "zapasu" = lepsze wykorzystanie
    infrastruktury portu), oraz te z dodatkowymi udogodnieniami.
    """
    score = 100.0
    reasons = []

    if specs:
        if specs.draft_meters is not None and berth.max_draft_meters is not None:
            margin = float(berth.max_draft_meters) - float(specs.draft_meters)
            score -= margin * 2  # mniejszy zapas = lepiej dopasowane nabrzeże
            reasons.append(f"zapas zanurzenia: {margin:.1f}m")

        if specs.length_overall_meters is not None and berth.max_loa_meters is not None:
            margin = float(berth.max_loa_meters) - float(specs.length_overall_meters)
            score -= margin * 0.5
            reasons.append(f"zapas LOA: {margin:.1f}m")

    if berth.has_shore_power:
        score += 5
        reasons.append("ma prąd z lądu")

    if berth.crane_capacity_tonnes:
        score += min(float(berth.crane_capacity_tonnes) / 10, 10)
        reasons.append(f"żuraw {berth.crane_capacity_tonnes}t")

    return score, reasons


def recommend_top_berths(
        db: Session,
        port_id: uuid.UUID,
        cargo_items: List[CargoManifest],
        vessel_specs: Optional[VesselTechnicalSpecs] = None,
        eta: Optional[datetime] = None,
        etd: Optional[datetime] = None,
        top_n: int = 3,
) -> List[BerthCandidate]:
    """
    Wybiera do top_n najlepszych nabrzeż w porcie dla danej nominacji.

    Dwuetapowo:
      1. FILTR BEZPIECZEŃSTWA (wykluczenie, nie punktacja) - nabrzeże,
         które fizycznie nie pomieści statku (draft/LOA/DWT) albo nie
         obsługuje wymaganego typu ładunku (reefer/niebezpieczny), albo
         jest zajęte w oknie ETA-ETD, jest CAŁKOWICIE wykluczone z listy,
         nawet jeśli zostanie mniej niż top_n wyników.
      2. SCORING OPTYMALNOŚCI - wśród tego, co przeszło filtr,
         sortujemy po dopasowaniu wymiarów i udogodnieniach.

    Zwraca listę BerthCandidate (max top_n), sortowaną od najlepszego.
    Pusta lista oznacza: żadne nabrzeże w porcie nie spełnia wymogów
    bezpieczeństwa dla tego statku/ładunku - wymaga to ręcznej interwencji
    agenta portowego.
    """
    berths = port_repository.get_berths_by_port(db, port_id)
    requirements = _vessel_requirements(cargo_items)

    candidates = []
    for berth in berths:
        rejection_reason = _passes_safety_filter(
            berth, vessel_specs,
            requirements["requires_reefer"], requirements["requires_dangerous_goods"],
            db, eta, etd,
        )
        if rejection_reason is not None:
            continue  # bezwzględnie wykluczone - nie trafia do listy w ŻADNEJ formie

        score, reasons = _score_berth(berth, vessel_specs)
        candidates.append(BerthCandidate(berth=berth, score=score, reasons=reasons))

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:top_n]


def recommend_berths_for_nomination(db: Session, nomination: Nomination, top_n: int = 3) -> List[BerthCandidate]:
    """
    Wygodny wrapper: dociąga cargo i najnowsze dane techniczne statku dla
    podanej nominacji, i zwraca TOP-N nabrzeż w jej porcie docelowym.
    """
    if not nomination.destination_port_id:
        return []

    cargo_items = db.query(CargoManifest).filter(
        CargoManifest.nomination_id == nomination.nomination_id
    ).all()

    vessel_specs = None
    if nomination.vessel_id:
        vessel_specs = db.query(VesselTechnicalSpecs).filter(
            VesselTechnicalSpecs.vessel_id == nomination.vessel_id
        ).order_by(VesselTechnicalSpecs.created_at.desc()).first()

    return recommend_top_berths(
        db,
        nomination.destination_port_id,
        cargo_items=cargo_items,
        vessel_specs=vessel_specs,
        eta=nomination.eta,
        etd=nomination.etd,
        top_n=top_n,
    )
from unittest.mock import MagicMock, patch
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from app.services.berth_assignment_service import recommend_best_berth, recommend_top_berths
from app.models.reference import Berth
from app.models.vessel import VesselTechnicalSpecs
from app.models.operations import CargoManifest
from app.models.enums import ImdgHazardClass


@patch("app.repositories.port_repository.get_berths_by_port")
def test_recommend_berth_for_reefer_cargo(mock_get_berths):
    mock_db = MagicMock()
    port_id = uuid.uuid4()

    # Przygotowujemy listę dostępnych nabrzeży (jedno zwykłe, jedno "igloport")
    berth_standard = Berth(berth_name="Standard Terminal", supports_reefer_containers=False)
    berth_reefer = Berth(berth_name="Igloport Gdynia", supports_reefer_containers=True)

    mock_get_berths.return_value = [berth_standard, berth_reefer]

    # Test 1: Ładunek wymaga chłodzenia (np. mrożonki z notatek)
    best_berth = recommend_best_berth(mock_db, port_id, requires_reefer=True, is_dangerous=False)
    assert best_berth.berth_name == "Igloport Gdynia"

    # Test 2: Ładunek nie wymaga chłodzenia
    best_berth_standard = recommend_best_berth(mock_db, port_id, requires_reefer=False, is_dangerous=False)
    assert best_berth_standard.berth_name == "Standard Terminal"  # Powinien złapać pierwsze lepsze


def _make_berth(name, draft=15.0, loa=250.0, dwt=80000.0, reefer=False, dangerous=False,
                 shore_power=False, crane=None, is_active=True):
    return Berth(
        berth_id=uuid.uuid4(),
        berth_code=name[:10],
        berth_name=name,
        max_draft_meters=Decimal(str(draft)),
        max_loa_meters=Decimal(str(loa)),
        max_dwt_tonnes=Decimal(str(dwt)),
        supports_reefer_containers=reefer,
        supports_dangerous_goods=dangerous,
        has_shore_power=shore_power,
        crane_capacity_tonnes=Decimal(str(crane)) if crane else None,
        is_active=is_active,
    )


def _make_specs(draft=10.0, loa=180.0, dwt=40000.0):
    return VesselTechnicalSpecs(
        draft_meters=Decimal(str(draft)),
        length_overall_meters=Decimal(str(loa)),
        deadweight_tonnage=Decimal(str(dwt)),
    )


def _make_cargo(requires_refrigeration=False, imdg=ImdgHazardClass.none):
    return CargoManifest(
        cargo_description="Test cargo",
        requires_refrigeration=requires_refrigeration,
        imdg_hazard_class=imdg,
    )


@patch("app.repositories.port_repository.is_berth_occupied_during")
@patch("app.repositories.port_repository.get_berths_by_port")
def test_recommend_top_berths_excludes_berth_too_small_for_vessel_draft(mock_get_berths, mock_occupied):
    """Statek z większym zanurzeniem niż max nabrzeża MUSI być wykluczony
    z listy - to jest bezwzględny wymóg bezpieczeństwa, nie punktacja."""
    mock_db = MagicMock()
    mock_occupied.return_value = False

    too_shallow = _make_berth("Płytkie nabrzeże", draft=8.0)  # statek ma draft 12m
    deep_enough = _make_berth("Głębokie nabrzeże", draft=15.0)
    mock_get_berths.return_value = [too_shallow, deep_enough]

    specs = _make_specs(draft=12.0)
    results = recommend_top_berths(mock_db, uuid.uuid4(), cargo_items=[], vessel_specs=specs)

    berth_names = {c.berth.berth_name for c in results}
    assert "Płytkie nabrzeże" not in berth_names
    assert "Głębokie nabrzeże" in berth_names


@patch("app.repositories.port_repository.is_berth_occupied_during")
@patch("app.repositories.port_repository.get_berths_by_port")
def test_recommend_top_berths_excludes_berth_without_dangerous_goods_support(mock_get_berths, mock_occupied):
    """Ładunek niebezpieczny (IMDG != none) wymaga nabrzeża z
    supports_dangerous_goods=True - inne nabrzeża są wykluczone."""
    mock_db = MagicMock()
    mock_occupied.return_value = False

    no_dangerous = _make_berth("Zwykłe nabrzeże", dangerous=False)
    dangerous_ok = _make_berth("Nabrzeże DG", dangerous=True)
    mock_get_berths.return_value = [no_dangerous, dangerous_ok]

    cargo = [_make_cargo(imdg=ImdgHazardClass.class_3_flammable_liquids)]
    results = recommend_top_berths(mock_db, uuid.uuid4(), cargo_items=cargo, vessel_specs=None)

    berth_names = {c.berth.berth_name for c in results}
    assert "Zwykłe nabrzeże" not in berth_names
    assert "Nabrzeże DG" in berth_names


@patch("app.repositories.port_repository.is_berth_occupied_during")
@patch("app.repositories.port_repository.get_berths_by_port")
def test_recommend_top_berths_excludes_occupied_berth_in_time_window(mock_get_berths, mock_occupied):
    """Nabrzeże zajęte w oknie ETA-ETD jest wykluczone, nawet jeśli
    spełnia wszystkie inne wymogi."""
    mock_db = MagicMock()

    free_berth = _make_berth("Wolne nabrzeże")
    busy_berth = _make_berth("Zajęte nabrzeże")
    mock_get_berths.return_value = [free_berth, busy_berth]

    def occupied_side_effect(db, berth_id, start, end):
        return berth_id == busy_berth.berth_id

    mock_occupied.side_effect = occupied_side_effect

    eta = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    etd = datetime(2026, 7, 2, 18, 0, tzinfo=timezone.utc)
    results = recommend_top_berths(mock_db, uuid.uuid4(), cargo_items=[], vessel_specs=None, eta=eta, etd=etd)

    berth_names = {c.berth.berth_name for c in results}
    assert "Zajęte nabrzeże" not in berth_names
    assert "Wolne nabrzeże" in berth_names


@patch("app.repositories.port_repository.is_berth_occupied_during")
@patch("app.repositories.port_repository.get_berths_by_port")
def test_recommend_top_berths_returns_empty_list_when_nothing_passes_safety_filter(mock_get_berths, mock_occupied):
    """Jeśli ŻADNE nabrzeże nie spełnia wymogów bezpieczeństwa, wynik
    jest pustą listą (a nie np. listą z 'najmniej złym' wyborem)."""
    mock_db = MagicMock()
    mock_occupied.return_value = False

    only_shallow = _make_berth("Jedyne nabrzeże", draft=5.0)
    mock_get_berths.return_value = [only_shallow]

    specs = _make_specs(draft=20.0)  # za duży statek na to nabrzeże
    results = recommend_top_berths(mock_db, uuid.uuid4(), cargo_items=[], vessel_specs=specs)

    assert results == []


@patch("app.repositories.port_repository.is_berth_occupied_during")
@patch("app.repositories.port_repository.get_berths_by_port")
def test_recommend_top_berths_respects_top_n_limit(mock_get_berths, mock_occupied):
    mock_db = MagicMock()
    mock_occupied.return_value = False

    berths = [_make_berth(f"Nabrzeże {i}") for i in range(5)]
    mock_get_berths.return_value = berths

    results = recommend_top_berths(mock_db, uuid.uuid4(), cargo_items=[], vessel_specs=None, top_n=3)

    assert len(results) == 3


@patch("app.repositories.port_repository.is_berth_occupied_during")
@patch("app.repositories.port_repository.get_berths_by_port")
def test_recommend_top_berths_scores_better_fit_higher(mock_get_berths, mock_occupied):
    """Wśród nabrzeży, które przeszły filtr bezpieczeństwa, lepiej
    dopasowane wymiarowo (mniejszy 'zapas') powinno mieć wyższy score."""
    mock_db = MagicMock()
    mock_occupied.return_value = False

    tight_fit = _make_berth("Dopasowane", draft=12.5, loa=185.0)   # statek: draft 12, loa 180
    loose_fit = _make_berth("Za duże", draft=25.0, loa=350.0)
    mock_get_berths.return_value = [tight_fit, loose_fit]

    specs = _make_specs(draft=12.0, loa=180.0)
    results = recommend_top_berths(mock_db, uuid.uuid4(), cargo_items=[], vessel_specs=specs)

    assert results[0].berth.berth_name == "Dopasowane"
    assert results[0].score > results[1].score


@patch("app.repositories.port_repository.is_berth_occupied_during")
@patch("app.repositories.port_repository.get_berths_by_port")
def test_recommend_top_berths_excludes_inactive_berth(mock_get_berths, mock_occupied):
    mock_db = MagicMock()
    mock_occupied.return_value = False

    inactive = _make_berth("Wyłączone z użytku", is_active=False)
    active = _make_berth("Aktywne")
    mock_get_berths.return_value = [inactive, active]

    results = recommend_top_berths(mock_db, uuid.uuid4(), cargo_items=[], vessel_specs=None)

    berth_names = {c.berth.berth_name for c in results}
    assert "Wyłączone z użytku" not in berth_names
    assert "Aktywne" in berth_names


@patch("app.repositories.port_repository.is_berth_occupied_during")
@patch("app.repositories.port_repository.get_berths_by_port")
def test_recommend_top_berths_does_not_block_without_eta_etd(mock_get_berths, mock_occupied):
    """Bez podanych ETA/ETD nie sprawdzamy kolizji czasowej (nie ma
    czego sprawdzić) - nabrzeże nie jest blokowane z tego powodu."""
    mock_db = MagicMock()
    berth = _make_berth("Nabrzeże bez dat")
    mock_get_berths.return_value = [berth]

    results = recommend_top_berths(mock_db, uuid.uuid4(), cargo_items=[], vessel_specs=None, eta=None, etd=None)

    assert len(results) == 1
    mock_occupied.assert_not_called()
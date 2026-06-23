from unittest.mock import MagicMock, patch
import uuid
from app.services.berth_assignment_service import recommend_best_berth
from app.models.reference import Berth


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
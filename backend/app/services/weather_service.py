import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def get_port_weather(lat: float, lon: float) -> Dict[str, Any]:
    """
    Pobiera pogodę (np. ze StormGlass.io).
    To jest kluczowe dla agenta, by wiedzieć o opóźnieniach wywołanych falą/wiatrem.
    """
    # MOCK_MODE: Na hackathonie zwykle oszczędza się limit zapytań i zwraca twarde dane
    mock_weather = {
        "wind_speed_knots": 15.2,
        "wind_direction_degrees": 210,
        "wave_height_meters": 1.5,
        "air_temperature_celsius": 12.0,
        "warning_active": False,
        "notes": "Warunki optymalne do manewrów portowych."
    }

    # Jeśli na prezentacji chcecie prawdziwe dane, podmieńcie poniższy kod:
    """
    API_KEY = "stormglass_key"
    url = f"https://api.stormglass.io/v2/weather/point?lat={lat}&lng={lon}&params=windSpeed,waveHeight"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers={"Authorization": API_KEY}, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                return data # (tutaj mapowanie odpowiedzi StormGlass na nasz dict)
    except Exception as e:
        logger.error(f"Weather API Error: {e}")
    """

    return mock_weather
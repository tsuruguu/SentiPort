import pytest
from app.services.weather_service import get_port_weather

@pytest.mark.asyncio
async def test_get_port_weather():
    weather = await get_port_weather(54.51, 18.54)
    assert "wind_speed_knots" in weather
    assert weather["wind_speed_knots"] == 15.2
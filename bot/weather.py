"""Погода и проверка жары (Sprint 6).

Один источник для двух мест: утренний бриф (перед прогулкой) и M7 (перед выездом
на тур). Используем Open-Meteo — бесплатно, без ключа. Координаты — из настроек
(дефолт Нови-Сад). Сеть может молчать/тупить → fetch_weather() всегда возвращает
None при любой ошибке, и вызывающий просто опускает строку про жару (пуш не падает).

Пороги жары — из BLUMER_SYSTEM §4: лаготто не брахицефал, но при +30 и выше
прогулки только утром/вечером, вода с собой, не оставлять в машине.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiohttp

log = logging.getLogger(__name__)

_API = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = 6  # сек: лучше тихо пропустить, чем задержать пуш

# Пороги (°C по дневному максимуму).
HEAT_HOT = 30   # серьёзно: только утро/вечер, не оставлять в машине
HEAT_WARM = 25  # умеренно: тень, вода с собой


@dataclass(frozen=True)
class Weather:
    temp_now: float | None
    temp_max: float | None

    @property
    def peak(self) -> float | None:
        """Ориентир для предупреждения — берём максимум из текущей и дневной."""
        vals = [v for v in (self.temp_now, self.temp_max) if v is not None]
        return max(vals) if vals else None


async def fetch_weather(lat: float, lon: float) -> Weather | None:
    """Текущая температура + дневной максимум. None при любой сетевой ошибке."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m",
        "daily": "temperature_2m_max",
        "timezone": "auto",
        "forecast_days": 1,
    }
    try:
        timeout = aiohttp.ClientTimeout(total=_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(_API, params=params) as r:
                r.raise_for_status()
                data = await r.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        log.warning("Погода недоступна: %s", e)
        return None

    now = (data.get("current") or {}).get("temperature_2m")
    daily = (data.get("daily") or {}).get("temperature_2m_max") or []
    tmax = daily[0] if daily else None
    return Weather(temp_now=now, temp_max=tmax)


def heat_level(temp: float | None) -> str:
    """'hot' | 'warm' | 'ok' | 'unknown'."""
    if temp is None:
        return "unknown"
    if temp >= HEAT_HOT:
        return "hot"
    if temp >= HEAT_WARM:
        return "warm"
    return "ok"


def heat_advice(w: Weather | None) -> tuple[str, str] | None:
    """(level, строка) для жаркой/тёплой погоды. None — если прохладно/неизвестно.

    Используется в утреннем брифе: молчим, когда не жарко, чтобы не шуметь.
    """
    if w is None:
        return None
    peak = w.peak
    level = heat_level(peak)
    if level == "hot":
        return level, (
            f"🥵 <b>Жара ~{peak:.0f}°C.</b> Прогулки только утром и вечером, "
            f"вода с собой, тень, лапы беречь от раскалённого асфальта. "
            f"Блумера <b>никогда</b> не оставлять в машине."
        )
    if level == "warm":
        return level, (
            f"🌡 Тепло ~{peak:.0f}°C. Возьми воду, держись тени, "
            f"в полдень активность пониже."
        )
    return None


def heat_line_always(w: Weather | None) -> str:
    """Строка про погоду для контекста выезда (M7): отвечаем всегда, даже когда ок."""
    advice = heat_advice(w)
    if advice is not None:
        return advice[1]
    if w is None or w.peak is None:
        return "🌡 Погоду сейчас не достать — проверь прогноз перед выездом сам."
    return f"🌤 ~{w.peak:.0f}°C — комфортно. Вода с собой не помешает."

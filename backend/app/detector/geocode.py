"""Traduce lat/lon a un label legible con la Geocoding API de Google.

Se llama solo cuando el detector emite un evento, nunca en cada ping, y ademas
cachea en Redis: la Geocoding API se paga por request.
"""
import logging

import httpx

from ..config import GOOGLE_MAPS_API_KEY
from ..state import r as redis_client

log = logging.getLogger("geocode")
URL = "https://maps.googleapis.com/maps/api/geocode/json"
MAX_LEN = 240  # el contrato limita location_label a 240 caracteres


async def label(lat, lon):
    """Direccion legible del punto. Cae a las coordenadas si no se puede."""
    fallback = f"{lat:.4f}, {lon:.4f}"
    if not GOOGLE_MAPS_API_KEY:
        return fallback

    # 3 decimales ~ 110 m: dos paradas cercanas no se pagan dos veces
    key = f"geo:{lat:.3f},{lon:.3f}"
    cached = await redis_client.get(key)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get(URL, params={
                "latlng": f"{lat},{lon}", "key": GOOGLE_MAPS_API_KEY, "language": "es"})
        data = res.json()
        if data.get("status") != "OK" or not data.get("results"):
            log.warning("geocoding sin resultado (%s), uso coordenadas", data.get("status"))
            return fallback
        out = data["results"][0]["formatted_address"][:MAX_LEN]
    except Exception:
        log.exception("geocoding fallo, uso coordenadas")
        return fallback

    await redis_client.set(key, out, ex=86400)
    return out

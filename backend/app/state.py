"""Memoria volatil en Redis: ultimo ping, ventanas moviles, locks anti-spam."""
import json

import redis.asyncio as redis

from .config import REDIS_URL

r = redis.from_url(REDIS_URL, decode_responses=True)


async def set_last(trip_id, ping):
    await r.set(f"last:{trip_id}", json.dumps(ping), ex=3600)


async def get_last(trip_id):
    v = await r.get(f"last:{trip_id}")
    return json.loads(v) if v else None


async def push_window(trip_id, ping, keep=20):
    """Ventana movil de pings para calcular velocidad promedio / detectar paradas."""
    k = f"win:{trip_id}"
    await r.lpush(k, json.dumps(ping))
    await r.ltrim(k, 0, keep - 1)
    await r.expire(k, 3600)


async def get_window(trip_id):
    return [json.loads(v) for v in await r.lrange(f"win:{trip_id}", 0, -1)]


async def once(key, ttl=600):
    """Devuelve True solo la primera vez en `ttl` segundos. Evita llamar 10 veces."""
    return bool(await r.set(f"once:{key}", "1", ex=ttl, nx=True))


async def clear_trip(trip_id):
    await r.delete(f"last:{trip_id}", f"win:{trip_id}")

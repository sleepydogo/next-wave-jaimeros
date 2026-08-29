"""Memoria volatil en Redis: cola de pings, ultimo ping, ventanas, locks."""
import json

import redis.asyncio as redis

from .config import REDIS_URL

r = redis.from_url(REDIS_URL, decode_responses=True)

PING_QUEUE = "pings:queue"


async def push_ping(trip_id, ping):
    """La app encola su posicion. El detector la consume del otro lado."""
    await r.lpush(PING_QUEUE, json.dumps({"trip_id": trip_id, "ping": ping}))


async def pop_ping(timeout=5):
    """Espera bloqueante por el proximo ping. None si no llego nada en `timeout`.

    redis-py levanta TimeoutError cuando vence el BRPOP en vez de devolver nil.
    Para nosotros eso no es un fallo, es "no llego nada": lo traducimos a None.
    """
    try:
        item = await r.brpop(PING_QUEUE, timeout=timeout)
    except redis.TimeoutError:
        return None
    return json.loads(item[1]) if item else None


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

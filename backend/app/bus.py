"""Bus de eventos. RabbitMQ si hay RABBITMQ_URL, si no Redis pub/sub.

API unica:
    @bus.on(events.TRUCK_ARRIVED)
    async def handler(payload): ...

    await bus.publish(events.TRUCK_ARRIVED, {...})
"""
import asyncio
import json
import logging
import time

from . import db, events
from .config import RABBITMQ_URL
from .state import r as redis_client

log = logging.getLogger("bus")
CHANNEL = "nextwave"
_handlers: dict[str, list] = {}


def on(event_type):
    def deco(fn):
        _handlers.setdefault(event_type, []).append(fn)
        return fn
    return deco


async def publish(event_type, payload, event_id=None, ts=None):
    msg = events.envelope(event_type, payload, event_id, ts)
    db.log_event(payload.get("trip_id"), event_type, payload)
    log.info("publish %s %s", event_type, payload.get("trip_id"))
    if RABBITMQ_URL:
        await _amqp_publish(msg)
    else:
        await redis_client.publish(CHANNEL, json.dumps(msg))


async def _dispatch(msg):
    for fn in _handlers.get(msg["type"], []):
        try:
            await fn(msg["payload"], msg)
        except Exception:
            log.exception("handler %s fallo en %s", fn.__name__, msg["type"])


# ---------- redis backend ----------
async def _redis_consume():
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(CHANNEL)
    log.info("bus: redis pub/sub en %s", CHANNEL)
    async for m in pubsub.listen():
        if m["type"] == "message":
            await _dispatch(json.loads(m["data"]))


# ---------- rabbitmq backend ----------
_amqp_ex = None


async def _amqp_publish(msg):
    import aio_pika
    await _amqp_ex.publish(
        aio_pika.Message(json.dumps(msg).encode()), routing_key=""
    )


async def _amqp_consume():
    import aio_pika
    global _amqp_ex
    conn = await aio_pika.connect_robust(RABBITMQ_URL)
    ch = await conn.channel()
    _amqp_ex = await ch.declare_exchange(CHANNEL, aio_pika.ExchangeType.FANOUT)
    qu = await ch.declare_queue("nextwave.workers", durable=True)
    await qu.bind(_amqp_ex)
    log.info("bus: rabbitmq fanout %s", CHANNEL)
    async with qu.iterator() as it:
        async for m in it:
            async with m.process():
                await _dispatch(json.loads(m.body))


def start():
    """Arranca el consumer en background. Llamar desde el startup de FastAPI."""
    coro = _amqp_consume() if RABBITMQ_URL else _redis_consume()
    return asyncio.create_task(coro)

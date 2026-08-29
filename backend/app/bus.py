"""Bus de eventos. RabbitMQ si hay RABBITMQ_URL, si no Redis pub/sub.

API unica:
    @bus.on(events.TRUCK_ARRIVED)
    async def handler(payload): ...

    await bus.publish(events.TRUCK_ARRIVED, {...})
"""
import asyncio
import inspect
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
    log.info("publish event_id=%s type=%s trip_id=%s", msg["event_id"], event_type, payload.get("trip_id"))
    if RABBITMQ_URL:
        await _amqp_publish(msg)
    else:
        await redis_client.publish(CHANNEL, json.dumps(msg))


async def _dispatch(msg):
    if (msg.get("schema_version") != events.SCHEMA_VERSION or
            not msg.get("event_id") or not isinstance(msg.get("payload"), dict) or
            msg.get("type") not in events.ALL):
        log.error("evento invalido event_id=%s type=%s", msg.get("event_id"), msg.get("type"))
        return False
    ok = True
    for fn in _handlers.get(msg["type"], []):
        try:
            if len(inspect.signature(fn).parameters) >= 2:
                await fn(msg["payload"], msg)
            else:  # compatibilidad con handlers simples del prototipo
                await fn(msg["payload"])
        except Exception:
            log.exception("handler %s fallo en %s", fn.__name__, msg["type"])
            ok = False
    return ok


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
_amqp_conn = None
_amqp_ch = None
_amqp_ready = asyncio.Event()
_consumer_task = None


async def _amqp_publish(msg):
    import aio_pika
    await asyncio.wait_for(_amqp_ready.wait(), timeout=15)
    await _amqp_ex.publish(
        aio_pika.Message(json.dumps(msg).encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key=""
    )


async def _amqp_consume():
    import aio_pika
    global _amqp_ex, _amqp_conn, _amqp_ch
    _amqp_conn = await aio_pika.connect_robust(RABBITMQ_URL)
    _amqp_ch = await _amqp_conn.channel()
    await _amqp_ch.set_qos(prefetch_count=10)
    _amqp_ex = await _amqp_ch.declare_exchange(CHANNEL, aio_pika.ExchangeType.FANOUT, durable=True)
    dlx = await _amqp_ch.declare_exchange(f"{CHANNEL}.dlx", aio_pika.ExchangeType.FANOUT, durable=True)
    dead = await _amqp_ch.declare_queue(f"{CHANNEL}.dead", durable=True)
    await dead.bind(dlx)
    qu = await _amqp_ch.declare_queue("nextwave.workers", durable=True,
                                      arguments={"x-dead-letter-exchange": f"{CHANNEL}.dlx"})
    await qu.bind(_amqp_ex)
    _amqp_ready.set()
    log.info("bus: rabbitmq fanout %s", CHANNEL)
    try:
        async with qu.iterator() as it:
            async for m in it:
                try:
                    ok = await _dispatch(json.loads(m.body))
                    if ok:
                        await m.ack()
                    else:
                        await m.reject(requeue=False)
                except Exception:
                    log.exception("mensaje AMQP invalido")
                    await m.reject(requeue=False)
    finally:
        _amqp_ready.clear()


async def stop():
    """Detiene el consumer y cierra las conexiones del transporte."""
    global _consumer_task, _amqp_conn, _amqp_ch, _amqp_ex
    if _consumer_task and not _consumer_task.done():
        _consumer_task.cancel()
        await asyncio.gather(_consumer_task, return_exceptions=True)
    if _amqp_ch:
        await _amqp_ch.close()
    if _amqp_conn:
        await _amqp_conn.close()
    _consumer_task = None
    _amqp_ch = _amqp_conn = _amqp_ex = None


def start():
    """Arranca el consumer en background. Llamar desde el startup de FastAPI."""
    global _consumer_task
    coro = _amqp_consume() if RABBITMQ_URL else _redis_consume()
    _consumer_task = asyncio.create_task(coro)
    return _consumer_task

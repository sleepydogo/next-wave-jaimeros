import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import bus, db
from .agent import worker as agent_worker  # noqa: F401  (registra handlers)
from .api import driver, ops, twilio_hooks
from .detector import rules
from .dispatcher import worker as dispatcher_worker  # noqa: F401  (registra handlers)
from .jobs import threshold_agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)-12s %(message)s",
                    datefmt="%H:%M:%S")

DESCRIPTION = """
Automatiza el trabajo del **monitorista**: hoy una persona mira la posicion del
camion en una PC, llama al conductor cuando llega al puerto para ver si esta
disponible, y lo vuelve a llamar cuando el puerto habilita la carga.

La app del conductor manda su posicion, el **detector** decide si eso es un
hecho de negocio, lo publica en un **bus de eventos**, y del otro lado el
**agente** llama por telefono y el **dispatcher** manda las alertas.

```
app movil --ping--> detector --evento--> bus --> agente --> Twilio + OpenAI
                                          |
                                          +---> dispatcher (email / WhatsApp)
```

## Como probar todo, en orden

1. `POST /ops/seed` — crea conductor y viaje. Guardate el `trip_id`.
2. `POST /driver/ping` con `lat: -34.60, lon: -58.366, speed: 62` — lejos del
   puerto, no dispara nada (`status: en_ruta`).
3. `POST /driver/ping` con `lat: -34.5745, lon: -58.366, speed: 20` — entra al
   geofence (`status: en_puerto`) y **arranca la llamada**.
4. Esperar ~5 segundos y mirar `GET /ops/calls` para ver la transcripcion y las
   metricas de voz.
5. `POST /ops/trips/{trip_id}/port-ready` — habilita la carga, dispara la
   segunda llamada.
6. `GET /ops/metrics` — costo acumulado del agente vs. el humano.

Con `SIMULATE_CALLS=1` (el default) **no se gasta plata**: la llamada se simula
pero pasa igual por el brain, asi que el flujo que se prueba es el real.

## Estado del proyecto

El esquema de la base de datos es un **borrador sin acordar** y se esta
discutiendo en la rama `design/db-schema`. Ver `backend/README.md` antes de
construir encima.
"""

TAGS = [
    {"name": "driver",
     "description": "Lo que consume la **app movil** del conductor (React Native / Expo). "
                    "`POST /driver/ping` es el unico input del detector."},
    {"name": "ops",
     "description": "Lo que consume la **web de metricas** del monitorista (React). "
                    "Incluye los endpoints de demo (`seed`, `reset`)."},
    {"name": "twilio",
     "description": "**Webhooks que llama Twilio**, no el front. Devuelven TwiML (XML), no JSON. "
                    "Requieren `SIMULATE_CALLS=0`, credenciales de Twilio y `PUBLIC_URL` "
                    "apuntando a un ngrok."},
    {"name": "salud", "description": "Chequeo de vida."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    rules.seed()
    tasks = [bus.start(), asyncio.create_task(threshold_agent.loop())]
    logging.info("nextwave arriba")
    yield
    await bus.stop()
    for t in tasks[1:]:
        t.cancel()
    await asyncio.gather(*tasks[1:], return_exceptions=True)


app = FastAPI(
    title="NextWave — agente de voz para puertos",
    description=DESCRIPTION,
    version="0.1.0",
    openapi_tags=TAGS,
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(driver.router)
app.include_router(ops.router)
app.include_router(twilio_hooks.router)


@app.get("/health", tags=["salud"], summary="Ping de vida")
def health():
    """Devuelve `{"ok": true}` si el server esta arriba."""
    return {"ok": True}


@app.get("/ready", tags=["salud"], summary="Readiness de dependencias")
async def ready():
    """Indica si el transporte de eventos ya acepta publicaciones."""
    from fastapi import HTTPException
    from .config import RABBITMQ_URL
    if RABBITMQ_URL and not bus._amqp_ready.is_set():
        raise HTTPException(status_code=503, detail="RabbitMQ no esta listo")
    try:
        await bus.redis_client.ping()
    except Exception:
        raise HTTPException(status_code=503, detail="Redis no esta listo")
    return {"ok": True, "transport": "rabbitmq" if RABBITMQ_URL else "redis"}

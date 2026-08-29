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


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    rules.seed()
    tasks = [bus.start(), asyncio.create_task(threshold_agent.loop())]
    logging.info("nextwave arriba")
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="NextWave - agente de voz para puertos", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(driver.router)
app.include_router(ops.router)
app.include_router(twilio_hooks.router)


@app.get("/health")
def health():
    return {"ok": True}

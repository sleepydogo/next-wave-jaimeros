"""API de facturacion y remitos. Servicio aparte, datos estaticos.

Simula el sistema administrativo de la empresa, que en la realidad seria un ERP.
El agente de voz la consulta en vivo durante la llamada cuando el conductor
pregunta por una factura o un remito.
"""
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Facturacion y remitos", version="0.1.0")

# Mock estatico. La clave es el contenedor, que es lo que el conductor tiene
# a mano en el papel.
FACTURAS = {
    "MSCU-4471820": {
        "numero": "A-0001-00043821",
        "estado": "emitida",
        "monto_usd": 1840.00,
        "emitida_el": "2026-08-28",
        "vence_el": "2026-09-27",
        "observaciones": None,
    },
    "TCLU-9982314": {
        "numero": "A-0001-00043799",
        "estado": "pendiente",
        "monto_usd": 2310.50,
        "emitida_el": None,
        "vence_el": None,
        "observaciones": "Falta la conformidad del depósito para poder emitirla.",
    },
}

REMITOS = {
    "MSCU-4471820": {
        "numero": "R-0004-00012877",
        "estado": "listo_para_retirar",
        "puerta": "3",
        "preparado_el": "2026-08-29",
        "observaciones": "Retirar por puerta 3. Presentar DNI del conductor.",
    },
    "TCLU-9982314": {
        "numero": "R-0004-00012901",
        "estado": "en_preparacion",
        "puerta": None,
        "preparado_el": None,
        "observaciones": "Demora estimada de 40 minutos.",
    },
}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/facturas/{contenedor}", summary="Estado de la factura de un contenedor")
def factura(contenedor: str):
    """Devuelve el estado de facturacion. El agente lo lee en voz alta."""
    f = FACTURAS.get(contenedor.upper())
    if not f:
        raise HTTPException(404, f"no hay factura registrada para {contenedor}")
    return {"contenedor": contenedor.upper(), **f}


@app.get("/remitos/{contenedor}", summary="Estado del remito de un contenedor")
def remito(contenedor: str):
    r = REMITOS.get(contenedor.upper())
    if not r:
        raise HTTPException(404, f"no hay remito registrado para {contenedor}")
    return {"contenedor": contenedor.upper(), **r}

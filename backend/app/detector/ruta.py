"""Ruta real del viaje con la Routes API de Google, y ubicacion de los hitos.

Dos cosas:

1. La ruta que efectivamente maneja el camion (calles de verdad, no una recta).
2. Donde cae cada alerta sobre esa ruta. Los eventos de la demo se disparan con
   botones, asi que todos comparten la misma posicion y quedarian encimados en
   un solo pin. Los repartimos a lo largo del recorrido, en orden cronologico,
   cada `PASO_KM`, que es como se verian en un viaje real.
"""
import logging

import httpx

from ..config import GOOGLE_MAPS_API_KEY

log = logging.getLogger("ruta")

URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
PASO_KM = 3.0        # separacion entre hitos consecutivos sobre la ruta
CAMPOS = "routes.polyline.encodedPolyline,routes.distanceMeters,routes.duration"


def _decodificar(poly: str):
    """Polilinea codificada de Google -> lista de (lat, lon).

    Es el formato estandar de Google: cada coordenada se guarda como delta
    respecto de la anterior, en base64 de 5 bits por caracter.
    """
    puntos, i, lat, lon = [], 0, 0, 0
    while i < len(poly):
        for eje in range(2):
            resultado, shift = 0, 0
            while True:
                b = ord(poly[i]) - 63
                i += 1
                resultado |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(resultado >> 1) if resultado & 1 else (resultado >> 1)
            if eje == 0:
                lat += delta
            else:
                lon += delta
        puntos.append((lat / 1e5, lon / 1e5))
    return puntos


async def calcular(origen, destino):
    """Ruta real entre dos puntos. Cae a la recta si no se puede consultar."""
    recta = [origen, destino]
    if not GOOGLE_MAPS_API_KEY:
        return recta, "sin api key"
    cuerpo = {
        "origin": {"location": {"latLng": {"latitude": origen[0], "longitude": origen[1]}}},
        "destination": {"location": {"latLng": {"latitude": destino[0], "longitude": destino[1]}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.post(URL, json=cuerpo, headers={
                "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
                "X-Goog-FieldMask": CAMPOS,
            })
        data = r.json()
        rutas = data.get("routes") or []
        if not rutas:
            log.warning("routes api sin ruta: %s", str(data)[:200])
            return recta, "sin ruta"
        return _decodificar(rutas[0]["polyline"]["encodedPolyline"]), "ok"
    except Exception:
        log.exception("fallo la consulta de ruta")
        return recta, "error"


def _metros(a, b):
    """Distancia aproximada entre dos puntos, suficiente a esta escala."""
    import math
    mlat = math.radians((a[0] + b[0]) / 2)
    return math.hypot((b[1] - a[1]) * 111320 * math.cos(mlat),
                      (b[0] - a[0]) * 110540)


def repartir(puntos, cantidad):
    """Devuelve `cantidad` posiciones sobre la ruta, separadas ~PASO_KM.

    Arranca en el origen y avanza. Si la ruta es mas corta que lo que hace
    falta, reparte parejo para que igual no queden todos encimados.
    """
    if not puntos or cantidad <= 0:
        return []
    # distancia acumulada en cada vertice de la ruta
    acum, total = [0.0], 0.0
    for i in range(1, len(puntos)):
        total += _metros(puntos[i - 1], puntos[i])
        acum.append(total)

    paso = PASO_KM * 1000
    if paso * cantidad > total:          # la ruta no da: repartimos parejo
        paso = total / (cantidad + 1)

    salida = []
    for n in range(1, cantidad + 1):
        objetivo = min(paso * n, total)
        j = next((k for k, d in enumerate(acum) if d >= objetivo), len(puntos) - 1)
        salida.append({"lat": puntos[j][0], "lon": puntos[j][1],
                       "km": round(objetivo / 1000, 1)})
    return salida

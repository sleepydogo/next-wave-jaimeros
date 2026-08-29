"""Simulador de viaje: maneja la demo entera sin necesitar la app movil.

    python -m sim.simulate_trip llegada     # camion llega al puerto -> llamada
    python -m sim.simulate_trip parada      # se detiene en ruta -> emergencia
    python -m sim.simulate_trip frenada     # caida abrupta de velocidad
"""
import sys
import time

import httpx

API = "http://localhost:8000"

PUERTO = (-34.5745, -58.3660)      # Puerto Buenos Aires - Terminal 4
# la ruta va por tierra: si los pings caen en el rio, Google no devuelve
# ninguna direccion legible y location_label termina siendo las coordenadas
SALIDA = (-34.5560, -58.4400)      # zona Chacarita, ~7 km al noroeste del puerto
EN_RUTA = (-34.6037, -58.3816)     # Av. Corrientes al 1000, lejos del geofence


def estado(trip_id):
    """El estado real del viaje.

    No sirve leer la respuesta de /driver/ping: ese endpoint solo encola y
    devuelve el estado ANTERIOR, porque el detector consume la cola aparte.
    """
    for t in httpx.get(f"{API}/ops/trips", timeout=10).json():
        if t["id"] == trip_id:
            return t["status"]
    return "?"


def ping(trip_id, lat, lon, speed, espera=1.2):
    httpx.post(f"{API}/driver/ping",
               json={"trip_id": trip_id, "lat": lat, "lon": lon, "speed": speed}, timeout=10)
    time.sleep(espera)  # darle tiempo al detector a consumir antes de preguntar
    print(f"  ping ({lat:.4f},{lon:.4f}) {speed:>5.1f} km/h -> {estado(trip_id)}")


def acercarse(trip_id, pasos=6, speed=60.0):
    """Viene desde el noroeste hasta el puerto, por tierra."""
    for i in range(pasos):
        frac = i / (pasos - 1)
        lat = SALIDA[0] + (PUERTO[0] - SALIDA[0]) * frac
        lon = SALIDA[1] + (PUERTO[1] - SALIDA[1]) * frac
        ping(trip_id, lat, lon, speed)


def main():
    scenario = sys.argv[1] if len(sys.argv) > 1 else "llegada"

    # tiempos comprimidos para que la demo entre en 30 segundos
    httpx.post(f"{API}/ops/thresholds/stop_min_seconds", params={"value": 8})
    tid = httpx.post(f"{API}/ops/seed").json()["trip_id"]
    print(f"\n== escenario '{scenario}' | viaje {tid} ==\n")

    if scenario == "llegada":
        acercarse(tid)
        print("\n-> el camion entro al geofence. El agente deberia estar llamando.")
        time.sleep(12)
        print("-> el puerto habilita la carga...")
        httpx.post(f"{API}/ops/trips/{tid}/port-ready")
        print("-> segunda llamada en curso. Mira el dashboard.")

    elif scenario == "parada":
        for _ in range(3):
            ping(tid, EN_RUTA[0], EN_RUTA[1], 65.0)
        print("\n-> el camion se detiene en ruta...")
        for _ in range(8):
            ping(tid, EN_RUTA[0], EN_RUTA[1], 0.0, espera=1.5)
        print("-> emergencia disparada: llamada + alerta.")

    elif scenario == "frenada":
        ping(tid, EN_RUTA[0], EN_RUTA[1], 80.0)
        print("\n-> frenada brusca...")
        ping(tid, EN_RUTA[0] - 0.001, EN_RUTA[1], 8.0)
        print("-> emergencia disparada.")

    else:
        print(f"escenario desconocido: {scenario}")
        return

    time.sleep(10)
    m = httpx.get(f"{API}/ops/metrics").json()
    print(f"\nestado final del viaje: {estado(tid)}")
    print(f"costo agente: ${m['costo_agente_usd']} | humano equivalente: "
          f"${m['costo_humano_equivalente_usd']} | ahorro: ${m['ahorro_usd']}")


if __name__ == "__main__":
    main()

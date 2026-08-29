"""Simulador de viaje: maneja la demo entera sin necesitar la app movil.

    python -m sim.simulate_trip llegada     # camion llega al puerto -> llamada
    python -m sim.simulate_trip parada      # se detiene en ruta -> emergencia
    python -m sim.simulate_trip frenada     # caida abrupta de velocidad
"""
import sys
import time

import httpx

API = "http://localhost:8000"
PORT = (-34.5745, -58.3660)


def ping(trip_id, lat, lon, speed):
    r = httpx.post(f"{API}/driver/ping",
                   json={"trip_id": trip_id, "lat": lat, "lon": lon, "speed": speed}, timeout=10)
    print(f"  ping ({lat:.4f},{lon:.4f}) {speed:>5.1f} km/h -> {r.json()['status']}")


def approach(trip_id, steps=6, start_km=0.12, speed=60.0):
    """Se acerca al puerto desde el norte. start_km en grados de latitud (~0.12 = 13km)."""
    for i in range(steps):
        frac = i / (steps - 1)
        lat = PORT[0] + start_km * (1 - frac)
        ping(trip_id, lat, PORT[1], speed)
        time.sleep(1.2)


def main():
    scenario = sys.argv[1] if len(sys.argv) > 1 else "llegada"

    # tiempos comprimidos para que la demo entre en 30 segundos
    httpx.post(f"{API}/ops/thresholds/stop_min_seconds", params={"value": 8})
    trip = httpx.post(f"{API}/ops/seed").json()
    tid = trip["trip_id"]
    print(f"\n== escenario '{scenario}' | viaje {tid} ==\n")

    if scenario == "llegada":
        approach(tid)
        print("\n-> el camion entro al geofence. El agente deberia estar llamando.")
        time.sleep(12)
        print("-> el puerto habilita la carga...")
        httpx.post(f"{API}/ops/trips/{tid}/port-ready")
        print("-> segunda llamada en curso. Mira el dashboard.")

    elif scenario == "parada":
        for _ in range(3):
            ping(tid, PORT[0] + 0.10, PORT[1], 65.0)
            time.sleep(1.2)
        print("\n-> el camion se detiene en ruta...")
        for _ in range(8):
            ping(tid, PORT[0] + 0.10, PORT[1], 0.0)
            time.sleep(1.5)
        print("-> emergencia disparada: llamada + alerta.")

    elif scenario == "frenada":
        ping(tid, PORT[0] + 0.10, PORT[1], 80.0)
        time.sleep(1.2)
        print("\n-> frenada brusca...")
        ping(tid, PORT[0] + 0.099, PORT[1], 8.0)
        print("-> emergencia disparada.")

    else:
        print(f"escenario desconocido: {scenario}")
        return

    time.sleep(10)
    m = httpx.get(f"{API}/ops/metrics").json()
    print(f"\ncosto agente: ${m['costo_agente_usd']} | humano equivalente: "
          f"${m['costo_humano_equivalente_usd']} | ahorro: ${m['ahorro_usd']}")


if __name__ == "__main__":
    main()

#!/usr/bin/env bash
# Levanta todo NextWave: Redis, RabbitMQ, backend, web y mobile.
#
#   ./start.sh          levanta y deja datos de demo cargados
#   ./start.sh --clean  ademas borra la base y arranca de cero
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── Verificaciones previas ────────────────────────────────────────────────────

if ! docker info > /dev/null 2>&1; then
  echo "❌  Docker no esta corriendo. Abri Docker Desktop y volve a intentar."
  exit 1
fi

if ! command -v node > /dev/null 2>&1; then
  echo "❌  Node.js no esta instalado."
  exit 1
fi

# ── Limpieza opcional ─────────────────────────────────────────────────────────

if [[ "${1:-}" == "--clean" ]]; then
  echo "==> borrando datos previos"
  docker compose down -v > /dev/null 2>&1 || true
fi

# ── Docker: Redis + RabbitMQ + Backend ───────────────────────────────────────

echo "==> levantando redis, rabbitmq y backend"
docker compose up -d --build

echo "==> esperando a que el backend responda..."
for i in $(seq 1 60); do
  if curl -fs http://localhost:8000/health > /dev/null 2>&1; then
    echo "    backend listo ✓"
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo "❌  el backend no levanto. Logs:"
    docker compose logs --tail 40 backend
    exit 1
  fi
  sleep 2
done

# ── Datos de demo ─────────────────────────────────────────────────────────────

echo "==> cargando datos de demo"
SEED=$(curl -fs -X POST http://localhost:8000/ops/seed)
TRIP=$(echo "$SEED" | python3 -c "import sys,json;print(json.load(sys.stdin)['trip_id'])")

# un par de posiciones para que el dashboard no arranque vacio
curl -fs -X POST http://localhost:8000/driver/ping -H 'Content-Type: application/json' \
  -d "{\"trip_id\":\"$TRIP\",\"lat\":-34.60,\"lon\":-58.366,\"speed\":62}" > /dev/null
sleep 1
curl -fs -X POST http://localhost:8000/driver/ping -H 'Content-Type: application/json' \
  -d "{\"trip_id\":\"$TRIP\",\"lat\":-34.5745,\"lon\":-58.366,\"speed\":20}" > /dev/null

# ── Web (Vite) ────────────────────────────────────────────────────────────────

echo "==> instalando dependencias de web..."
(cd "$ROOT/web" && npm install --silent)

echo "==> arrancando web en http://localhost:5173"
(cd "$ROOT/web" && npm run dev) &
WEB_PID=$!

# ── Mobile (Expo) ─────────────────────────────────────────────────────────────

echo "==> instalando dependencias de mobile..."
(cd "$ROOT/mobile" && npm install --silent)

echo "==> arrancando mobile (Expo — escanea el QR con tu celular)"
(cd "$ROOT/mobile" && npx expo start) &
MOBILE_PID=$!

# ── Limpieza al salir (Ctrl+C) ────────────────────────────────────────────────

cleanup() {
  echo ""
  echo "==> apagando frontends..."
  kill "$WEB_PID" 2>/dev/null || true
  kill "$MOBILE_PID" 2>/dev/null || true
  echo "==> apagando docker..."
  docker compose down
  echo "==> todo apagado."
}
trap cleanup EXIT INT TERM

# ── Resumen ───────────────────────────────────────────────────────────────────

cat <<EOF

  ✅  Todo arriba.

  API .............. http://localhost:8000
  Swagger .......... http://localhost:8000/docs
  Web .............. http://localhost:5173
  Mobile ........... Expo (escanea el QR de arriba con Expo Go)
  RabbitMQ ......... http://localhost:15672   (guest / guest)

  Viaje de demo .... $TRIP
  Conductor ........ driver_01

  Probar:
    curl http://localhost:8000/ops/trips
    curl http://localhost:8000/ops/metrics

  Logs backend:  docker compose logs -f backend
  Apagar:        Ctrl+C

EOF

# Mantener vivo el script y esperar que ambos procesos terminen
wait "$WEB_PID" "$MOBILE_PID"

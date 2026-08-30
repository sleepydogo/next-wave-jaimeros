#!/usr/bin/env bash
# Levanta todo NextWave: Redis, RabbitMQ, backend, web y mobile.
#
#   ./start.sh          levanta y deja datos de demo cargados
#   ./start.sh --clean  ademas borra la base y arranca de cero
#   ./start.sh --calls  ademas levanta ngrok y hace llamadas REALES por Twilio
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

# ── Flags ─────────────────────────────────────────────────────────────────────

CLEAN=0
CALLS=0
for arg in "$@"; do
  case "$arg" in
    --clean) CLEAN=1 ;;
    --calls) CALLS=1 ;;
    *) echo "flag desconocido: $arg"; exit 1 ;;
  esac
done

if [[ $CLEAN -eq 1 ]]; then
  echo "==> borrando datos previos"
  docker compose down -v > /dev/null 2>&1 || true
fi

# ── Llamadas reales: chequear config antes de gastar plata ───────────────────

PROFILE=""
if [[ $CALLS -eq 1 ]]; then
  [[ -f .env ]] && set -a && . ./.env && set +a
  FALTAN=""
  for k in TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_FROM DEMO_WORKER_PHONE \
           NGROK_AUTHTOKEN NGROK_DOMAIN PUBLIC_URL OPENAI_API_KEY; do
    [[ -z "${!k:-}" ]] && FALTAN="$FALTAN $k"
  done
  if [[ -n "$FALTAN" ]]; then
    echo "❌  faltan estas variables en .env para llamar de verdad:"
    for k in $FALTAN; do echo "      $k"; done
    exit 1
  fi
  if [[ "${SIMULATE_CALLS:-1}" != "0" ]]; then
    echo "❌  poné SIMULATE_CALLS=0 en .env para que las llamadas salgan de verdad."
    exit 1
  fi
  if [[ "$PUBLIC_URL" != "https://$NGROK_DOMAIN" ]]; then
    echo "❌  PUBLIC_URL tiene que ser https://\$NGROK_DOMAIN"
    echo "      PUBLIC_URL=$PUBLIC_URL"
    echo "      esperado=https://$NGROK_DOMAIN"
    exit 1
  fi
  PROFILE="--profile voice"
  echo "==> modo LLAMADAS REALES: se va a llamar a $DEMO_WORKER_PHONE y gastar saldo"
fi

# ── Docker: Redis + RabbitMQ + Backend ───────────────────────────────────────

echo "==> levantando redis, rabbitmq y backend"
# sin comillas a proposito: PROFILE es "" o "--profile voice"
docker compose $PROFILE up -d --build

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

# Un par de posiciones para que el dashboard no arranque vacio.
# OJO: las dos quedan FUERA del geofence del puerto (-34.5745,-58.366, radio
# 800 m) a proposito. Si un ping entra, el detector dispara truck.arrived y el
# agente llama al conductor: con SIMULATE_CALLS=0 eso es una llamada real y
# paga, en cada arranque. Para provocar la llegada esta el simulador.
curl -fs -X POST http://localhost:8000/driver/ping -H 'Content-Type: application/json' \
  -d "{\"trip_id\":\"$TRIP\",\"lat\":-34.60,\"lon\":-58.366,\"speed\":62}" > /dev/null
sleep 1
curl -fs -X POST http://localhost:8000/driver/ping -H 'Content-Type: application/json' \
  -d "{\"trip_id\":\"$TRIP\",\"lat\":-34.59,\"lon\":-58.366,\"speed\":58}" > /dev/null

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
  RabbitMQ ......... http://localhost:15672   (guest / guest)$(
    [[ $CALLS -eq 1 ]] && printf '\n  ngrok ............ %s (inspector en http://localhost:4040)' "$PUBLIC_URL")

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

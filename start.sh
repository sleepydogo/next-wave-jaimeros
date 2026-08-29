#!/usr/bin/env bash
# Levanta todo NextWave: Redis, RabbitMQ y el backend. Un solo comando.
#
#   ./start.sh          levanta y deja datos de demo cargados
#   ./start.sh --clean  ademas borra la base y arranca de cero
set -euo pipefail

cd "$(dirname "$0")"

if ! docker info >/dev/null 2>&1; then
  echo "Docker no esta corriendo. Abri Docker Desktop y volve a intentar."
  exit 1
fi

if [[ "${1:-}" == "--clean" ]]; then
  echo "==> borrando datos previos"
  docker compose down -v >/dev/null 2>&1 || true
fi

echo "==> levantando redis, rabbitmq y backend (la primera vez tarda, compila la imagen)"
docker compose up -d --build

echo "==> esperando a que el backend responda"
for i in $(seq 1 60); do
  if curl -fs http://localhost:8000/health >/dev/null 2>&1; then break; fi
  if [[ $i -eq 60 ]]; then
    echo "el backend no levanto. Logs:"
    docker compose logs --tail 40 backend
    exit 1
  fi
  sleep 2
done

echo "==> cargando datos de demo"
SEED=$(curl -fs -X POST http://localhost:8000/ops/seed)
TRIP=$(echo "$SEED" | python3 -c "import sys,json;print(json.load(sys.stdin)['trip_id'])")

# un par de posiciones para que el dashboard no arranque vacio
curl -fs -X POST http://localhost:8000/driver/ping -H 'Content-Type: application/json' \
  -d "{\"trip_id\":\"$TRIP\",\"lat\":-34.60,\"lon\":-58.366,\"speed\":62}" >/dev/null
sleep 1
curl -fs -X POST http://localhost:8000/driver/ping -H 'Content-Type: application/json' \
  -d "{\"trip_id\":\"$TRIP\",\"lat\":-34.5745,\"lon\":-58.366,\"speed\":20}" >/dev/null

cat <<EOF

  Todo arriba.

  API .............. http://localhost:8000
  Swagger .......... http://localhost:8000/docs
  RabbitMQ ......... http://localhost:15672   (guest / guest)

  Viaje de demo .... $TRIP
  Conductor ........ driver_01

  Probar:  curl http://localhost:8000/ops/trips
           curl http://localhost:8000/ops/metrics

  Logs:    docker compose logs -f backend
  Apagar:  docker compose down

EOF

#!/usr/bin/env bash
# Deploy AzmoonRep on a server that already runs other Docker apps (e.g. Foroshgram).
# Uses plain `docker` (no compose: compose v1 is broken on the Foroshgram VPS) and its own
# network, volumes and ports, so it cannot touch the other containers.
#
#   scp -r azmoonrep taxonomy "main books"/books_catalog.json question_bank <server>:/opt/azmoon/
#   ssh <server> 'cd /opt/azmoon/azmoonrep && cp .env.example .env && nano .env && bash deploy/deploy.sh'
#
# Layout on the server (WORKSPACE, default /opt/azmoon):
#   azmoonrep/  taxonomy/  question_bank/  "main books"/books_catalog.json
set -euo pipefail

WORKSPACE="${WORKSPACE:-/opt/azmoon}"
cd "$WORKSPACE/azmoonrep"
[ -f .env ] || { echo "missing $WORKSPACE/azmoonrep/.env (copy .env.example)"; exit 1; }
set -a; . ./.env; set +a
: "${MONGO_USER:?}"; : "${MONGO_PASS:?}"; : "${JWT_SECRET:?}"
WEB_BIND="${WEB_BIND:-127.0.0.1}"       # 0.0.0.0 to publish without a reverse proxy
WEB_PORT="${WEB_PORT:-8081}"            # 3000, 3001, 5432, 9091 belong to Foroshgram
NET=azmoon_net

echo "== network and volumes"
docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET"
docker volume create azmoon_mongo >/dev/null
docker volume create azmoon_figures >/dev/null

if [ "${SKIP_BUILD:-0}" = "1" ]; then
  echo "== images: using the ones already loaded (SKIP_BUILD=1; docker load -i azmoon_images.tar.gz)"
  docker image inspect azmoon_api:latest azmoon_web:latest mongo:7 >/dev/null
else
  echo "== build images (backend, frontend)"
  docker build -t azmoon_api:latest ./backend
  docker build -t azmoon_web:latest ./frontend
fi

echo "== database (no published port: only the API can reach it)"
if ! docker ps -a --format '{{.Names}}' | grep -qx azmoon_mongo; then
  docker run -d --name azmoon_mongo --network "$NET" --restart unless-stopped \
    -v azmoon_mongo:/data/db \
    -e MONGO_INITDB_ROOT_USERNAME="$MONGO_USER" -e MONGO_INITDB_ROOT_PASSWORD="$MONGO_PASS" \
    mongo:7
  sleep 8
fi

echo "== api"
docker rm -f azmoon_api >/dev/null 2>&1 || true
docker run -d --name azmoon_api --network "$NET" --network-alias api --restart unless-stopped \
  -v azmoon_figures:/app/static/questions \
  -v "$WORKSPACE/question_bank":/data/question_bank:ro \
  -v "$WORKSPACE/taxonomy":/data/taxonomy:ro \
  -v "$WORKSPACE/main books":/data/main\ books:ro \
  -e APP_ENV=prod -e TRUST_PROXY=1 -e LOG_LEVEL=INFO \
  -e MONGO_URL=mongodb://azmoon_mongo:27017 -e MONGO_USER="$MONGO_USER" -e MONGO_PASS="$MONGO_PASS" \
  -e MONGO_DB=azmoonrep -e JWT_SECRET="$JWT_SECRET" \
  -e SMS_PROVIDER="${SMS_PROVIDER:-kavenegar}" -e SMS_API_KEY="${SMS_API_KEY:-}" \
  -e SMS_TEMPLATE="${SMS_TEMPLATE:-azmoonrep-otp}" \
  -e PASSWORD_LOGIN_FOR_STUDENTS="${PASSWORD_LOGIN_FOR_STUDENTS:-1}" \
  -e BOOKS_JSON="/data/main books/books_catalog.json" -e TAXONOMY_DIR=/data/taxonomy \
  -e QUESTIONS_ROOT=/data/question_bank \
  azmoon_api:latest

echo "== web"
docker rm -f azmoon_web >/dev/null 2>&1 || true
docker run -d --name azmoon_web --network "$NET" --restart unless-stopped \
  -p "$WEB_BIND:$WEB_PORT:80" azmoon_web:latest

echo "== wait for the API"
for i in $(seq 1 30); do
  if docker exec azmoon_api python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).status==200 else 1)" 2>/dev/null; then
    echo "api healthy"; break
  fi
  sleep 2
done

echo "== first-time data (safe to repeat: imports keep manager decisions)"
if [ -n "${MANAGER_PASSWORD:-}" ]; then
  docker exec -e MANAGER_PASSWORD="$MANAGER_PASSWORD" azmoon_api python -m scripts.seed_manager admin
fi
docker exec azmoon_api python -m scripts.import_data

echo
echo "Done. Web: http://$WEB_BIND:$WEB_PORT  (put the server's nginx/TLS in front for a public domain)"
echo "Logs:  docker logs -f azmoon_api      Status: docker ps --filter name=azmoon"

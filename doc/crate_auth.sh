#!/bin/bash
# Fija la clave del usuario 'crate' (CRATE_PASSWORD del .env). Idempotente.
# Se conecta por _local_ (trust, dentro del contenedor), asi que funciona antes y despues de activar la auth.
cd "$(dirname "$0")/.." || exit 1
set -a; . ./.env; set +a
for i in $(seq 1 60); do
  if docker exec db-crate crash -c "ALTER USER crate SET (password = '${CRATE_PASSWORD}');"; then
    echo "OK clave de crate fijada"; exit 0
  fi
  sleep 3
done
echo "FALLO: no se pudo fijar la clave de crate"; exit 1

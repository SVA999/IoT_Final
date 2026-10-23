#!/bin/bash
# Sincroniza las claves del .env con las que YA estan guardadas dentro de las bases de datos. Idempotente.
#
# Por que hace falta: con el disco de datos persistente (o tras restaurar un respaldo) las bases conservan los datos,
# y tambien la clave con la que se crearon. Postgres y CrateDB solo leen su clave al crear la base: si cambia en
# terraform.tfvars/.env, la base sigue con la vieja y el ETL y la API dejan de conectarse. Este script las iguala.
cd "$(dirname "$0")/.." || exit 1
set -a; . ./.env; set +a

docker compose up -d dwh crate-db >/dev/null

for i in $(seq 1 60); do   # esperar a Postgres (tope: 2 min)
  docker exec dwh-postgres pg_isready -U "$DWH_USER" -d "$DWH_DB" >/dev/null 2>&1 && break
  sleep 2
done
# Por el socket local del contenedor (sin clave): la clave nueva se fija desde .env
docker exec -i dwh-postgres psql -U "$DWH_USER" -d "$DWH_DB" -v ON_ERROR_STOP=1 \
  -c "ALTER USER \"$DWH_USER\" WITH PASSWORD '$DWH_PASSWORD';" >/dev/null \
  && echo "OK clave de Postgres sincronizada" || { echo "FALLO: no se pudo sincronizar la clave de Postgres"; exit 1; }

bash doc/crate_auth.sh   # crea/actualiza el usuario 'iot' de CrateDB con CRATE_PASSWORD

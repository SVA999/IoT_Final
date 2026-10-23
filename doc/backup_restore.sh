#!/bin/bash
# Respaldo y restauracion de TODOS los datos del sistema (volumenes de Docker):
#   mongo-db (Orion: entidades, suscripciones, dispositivos) · crate-db (historico crudo) · dwh-data (Postgres) · grafana
#
#   bash doc/backup_restore.sh backup  [carpeta]                 # detiene el sistema unos minutos y lo vuelve a iniciar
#   bash doc/backup_restore.sh restore <carpeta> [--yes] [--sin-arrancar]
#
# Uso tipico: pasar el historico de una instancia a otra (ver doc/GUIA_DESPLIEGUE_AWS.md, seccion "Migrar datos").
set -euo pipefail
export MSYS_NO_PATHCONV=1                      # Git Bash en Windows: que no reescriba las rutas
cd "$(dirname "$0")/.."

PROYECTO="${COMPOSE_PROJECT_NAME:-$(basename "$PWD" | tr 'A-Z' 'a-z')}"   # compose nombra los volumenes <proyecto>_<volumen>
VOLUMENES="mongo-db crate-db dwh-data grafana"
IMAGEN=alpine

ruta_abs() { mkdir -p "$1"; (cd "$1" && (pwd -W 2>/dev/null || pwd)); }

backup() {
  local destino="${1:-backups/$(date +%Y-%m-%d_%H%M)}" dir
  dir=$(ruta_abs "$destino")
  echo "Deteniendo el sistema para un respaldo consistente (vuelve a iniciar al terminar)..."
  docker compose stop >/dev/null
  trap 'docker compose start >/dev/null && echo "Sistema iniciado de nuevo."' EXIT
  for v in $VOLUMENES; do
    if ! docker volume inspect "${PROYECTO}_$v" >/dev/null 2>&1; then echo "-- sin volumen $v: se omite"; continue; fi
    docker run --rm -v "${PROYECTO}_$v":/datos:ro -v "$dir":/respaldo "$IMAGEN" tar czf "/respaldo/$v.tar.gz" -C /datos .
    echo "OK  $v  ($(du -h "$destino/$v.tar.gz" | cut -f1))"
  done
  echo "Respaldo en: $destino"
}

restore() {
  local origen="${1:?falta la carpeta del respaldo}" dir confirma="no" arrancar="si"; shift || true
  for a in "$@"; do [ "$a" = "--yes" ] && confirma="si"; [ "$a" = "--sin-arrancar" ] && arrancar="no"; done
  [ -d "$origen" ] || { echo "No existe la carpeta $origen"; exit 1; }
  dir=$(ruta_abs "$origen")
  ls "$origen"/*.tar.gz >/dev/null 2>&1 || { echo "No hay archivos .tar.gz en $origen"; exit 1; }
  if [ "$confirma" != "si" ]; then
    read -r -p "Esto REEMPLAZA los datos actuales por los del respaldo. Escribe SI para continuar: " r
    [ "$r" = "SI" ] || { echo "Cancelado."; exit 1; }
  fi
  docker compose down >/dev/null            # quita contenedores, CONSERVA los volumenes
  for v in $VOLUMENES; do
    [ -f "$origen/$v.tar.gz" ] || { echo "-- el respaldo no tiene $v: se omite"; continue; }
    docker volume create "${PROYECTO}_$v" >/dev/null
    docker run --rm -v "${PROYECTO}_$v":/datos -v "$dir":/respaldo:ro "$IMAGEN" \
      sh -c "rm -rf /datos/* /datos/.[!.]* 2>/dev/null; tar xzf /respaldo/$v.tar.gz -C /datos"
    echo "OK  $v restaurado"
  done
  if [ "$arrancar" = "si" ]; then
    docker compose up -d --build crate-db dwh
    bash doc/sync_claves.sh                  # las bases traen sus claves viejas: se igualan con el .env
    docker compose up -d --build
    echo "Sistema iniciado con los datos restaurados."
  fi
}

case "${1:-}" in
  backup)  shift; backup "$@" ;;
  restore) shift; restore "$@" ;;
  *) echo "Uso: bash doc/backup_restore.sh backup [carpeta] | restore <carpeta> [--yes] [--sin-arrancar]"; exit 1 ;;
esac

#!/bin/bash
# Provisiona el Agente IoT JSON, el dispositivo y la suscripcion Orion -> QuantumLeap.
# Es idempotente: si algo ya existe (409) se considera correcto. Falla (exit 1) si hay otro error.
# Uso: bash doc/provisionar.sh [HOST]      HOST = localhost si se corre en la EC2.
HOST=${1:-localhost}
APIKEY=plantas2026
FALLO=0

post() {  # post <nombre> <url> <json>
  local code
  code=$(curl -s -o /tmp/prov.out -w '%{http_code}' -X POST "$2" \
    -H 'fiware-service: openiot' -H 'fiware-servicepath: /' -H 'Content-Type: application/json' -d "$3")
  case "$code" in
    200|201|204|409) echo "OK   $1 (HTTP $code)";;
    *) echo "FALLO $1 (HTTP $code): $(cat /tmp/prov.out)"; FALLO=1;;
  esac
}

del() {  # del <url>   (ignora 404: puede no existir)
  curl -s -o /dev/null -X DELETE "$1" -H 'fiware-service: openiot' -H 'fiware-servicepath: /'
}

# 0) Limpiar registros viejos o mal mapeados (un 409 escondia dispositivos con atributos sin mapear)
del "http://$HOST:4041/iot/devices/planta01"
del "http://$HOST:4041/iot/services?resource=/iot/json&apikey=$APIKEY"
del "http://$HOST:1036/v2/entities/PlantSensor:planta01?type=PlantSensor"   # entidad autocreada sin mapeo
del "http://$HOST:1036/v2/entities/planta01?type=PlantSensor"

# 1) Grupo de servicio (apikey -> tipo de entidad)
post "grupo de servicio" "http://$HOST:4041/iot/services" '{
  "services": [{"apikey": "'$APIKEY'", "cbroker": "http://orion:1026",
                "entity_type": "PlantSensor", "resource": "/iot/json"}]}'

# 2) Dispositivo planta01. object_id = clave EXACTA del JSON que envia el firmware.
post "dispositivo planta01" "http://$HOST:4041/iot/devices" '{
  "devices": [{"device_id": "planta01", "entity_name": "planta01", "entity_type": "PlantSensor",
    "attributes": [
      {"object_id": "temperatura_aire",   "name": "temperature",  "type": "Number"},
      {"object_id": "humedad_aire",       "name": "humidity",     "type": "Number"},
      {"object_id": "luz_lux",            "name": "luminosity",   "type": "Number"},
      {"object_id": "humedad_suelo_pct",  "name": "soilMoisture", "type": "Number"}]}]}'

# 3) Suscripcion Orion -> QuantumLeap (tabla: mtopeniot.etplantsensor). Solo si no existe ya (evita duplicados).
if curl -s "http://$HOST:1036/v2/subscriptions" -H 'fiware-service: openiot' -H 'fiware-servicepath: /'      | grep -q 'Historico de plantas en QuantumLeap'; then
  echo "OK   suscripcion Orion->QuantumLeap (ya existia)"
else
  post "suscripcion Orion->QuantumLeap" "http://$HOST:1036/v2/subscriptions" '{
  "description": "Historico de plantas en QuantumLeap",
  "subject": {"entities": [{"idPattern": ".*", "type": "PlantSensor"}],
              "condition": {"attrs": ["temperature","humidity","luminosity","soilMoisture"]}},
  "notification": {"http": {"url": "http://quantumleap:8668/v2/notify"},
                   "attrs": ["temperature","humidity","luminosity","soilMoisture"],
                   "metadata": ["dateCreated","dateModified"]}}'
fi

exit $FALLO

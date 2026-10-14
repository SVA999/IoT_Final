#!/bin/bash
# Provisiona el Agente IoT JSON, el dispositivo y la suscripcion Orion -> QuantumLeap.
# Ejecutar una vez, tras `docker compose up -d`. HOST = IP del servidor (o localhost en la EC2).
HOST=${1:-localhost}
APIKEY=plantas2026
H=(-H 'fiware-service: openiot' -H 'fiware-servicepath: /' -H 'Content-Type: application/json')

# 1) Grupo de servicio (mapea apikey -> tipo de entidad)
curl -iX POST "http://$HOST:4041/iot/services" "${H[@]}" -d '{
  "services": [{"apikey": "'$APIKEY'", "cbroker": "http://orion:1026",
                "entity_type": "PlantSensor", "resource": "/iot/json"}]}'

# 2) Dispositivo planta01 (object_id del firmware -> atributo NGSI)
curl -iX POST "http://$HOST:4041/iot/devices" "${H[@]}" -d '{
  "devices": [{"device_id": "planta01", "entity_name": "planta01", "entity_type": "PlantSensor",
    "attributes": [
      {"object_id": "t",   "name": "temperature", "type": "Number"},
      {"object_id": "h",   "name": "humidity",    "type": "Number"},
      {"object_id": "l",   "name": "luminosity",  "type": "Number"},
      {"object_id": "s",   "name": "soilMoisture","type": "Number"},
      {"object_id": "loc", "name": "location",    "type": "geo:point"}]}]}'

# 3) Suscripcion Orion -> QuantumLeap (tabla: mtopeniot.etplantsensor)
curl -iX POST "http://$HOST:1036/v2/subscriptions" "${H[@]}" -d '{
  "description": "Historico de plantas en QuantumLeap",
  "subject": {"entities": [{"idPattern": ".*", "type": "PlantSensor"}],
              "condition": {"attrs": ["temperature","humidity","luminosity","soilMoisture"]}},
  "notification": {"http": {"url": "http://quantumleap:8668/v2/notify"},
                   "attrs": ["temperature","humidity","luminosity","soilMoisture","location"],
                   "metadata": ["dateCreated","dateModified"]}}'

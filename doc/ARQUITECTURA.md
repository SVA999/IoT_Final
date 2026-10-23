# Arquitectura – Monitoreo de plantas (IoT Proyecto Final)

Basada en el diagrama de la pizarra del profesor ("Agricultura"). Los otros proyectos (p. ej. el robot) reutilizan **la misma arquitectura de nube**; solo cambia el dispositivo.

## 1. Flujo extremo a extremo

```
[Sensores I2C] -> [LilyGo: GPS+LoRa+WiFi] --WiFi/LoRa--> [Gateway] --HTTP--> [Agente IoT :7896]
                                                                                  |
                                                                                  v
                                   [Mongo] <-- [ORION :1026 (ext 1036)] --notif--> [QuantumLeap :8668]
                                                    ^                                    |
                                                    | alertas (lazo de retorno)          v
                                                    |                              [CrateDB :4200]
                                                    |                                    |
                                                    +------ [ETL Python: Limpiar -> Analizar]
                                                                                  |
                                                                                  v
                                                                       [Postgres DWH (interno)]
                                                                                  |
                                                                                  v
                                                                      [API FastAPI :8000] -- IA
                                                                                  |
                                                                                  v
                                                                   [Front nginx :80/443] (+ Grafana :3000)
```

## 1b. Todo por suscripciones y eventos (sin sondeo)
| Tramo | Mecanismo |
|---|---|
| Device → Agente → Orion | push HTTP / NGSI |
| Orion → QuantumLeap → Crate | **suscripción 1** de Orion (histórico crudo) |
| Orion → ETL → DWH | **suscripción 2** de Orion → servicio `processor` → ETL (en vivo, ~10 s tras cada lectura) |
| ETL → navegador | `pg_notify('eventos')` → API (`LISTEN`) → **WebSocket** `/api/ws` |
| ETL → Telegram | bandeja de salida `notificacion` + despachador (alertas y predicciones) |
| Alerta → Orion | el ETL publica la entidad `PlantAlert` (lazo de retorno de la pizarra) |

Lo único periódico es un **cron de seguridad cada 30 min**: si el procesador estuvo caído y se perdió un evento, el ETL recupera lo pendiente
(es idempotente). El front ya no sondea: se actualiza por eventos (con un plan B lento solo si el websocket está caído).
Las dos suscripciones las crea `doc/provisionar.sh`; se verifican con `curl <IP>:1036/v2/subscriptions -H 'fiware-service: openiot' -H 'fiware-servicepath: /'`.

## 2. Capas y mapeo a la pizarra

| Pizarra | Servicio | Tecnología | Notas |
|---|---|---|---|
| Montar sensor (I2C) | End device (fuera de alcance, lo hace otro equipo) | TTGO T-Beam + HDC1080 (T/H) + sensor de luz + humedad de suelo analógica | Solo definimos el contrato JSON de entrada (abajo) |
| Agente | `iot-agent` | `fiware/iotagent-json` | Traduce JSON del dispositivo a entidades NGSI |
| O + MongoDB | `orion`, `mongo-db` | `fiware/orion` (NGSI v2) | Estado actual de cada planta |
| QL | `quantumleap` | orchestracities/quantumleap | Suscripción Orion → serie de tiempo |
| CrateDB | `crate-db` | CrateDB | Histórico **crudo**; con autenticación (usuario `iot`, clave `CRATE_PASSWORD`) |
| Limpiar / Analizar | `etl` | Python | Limpia rangos, calcula agregados y alertas |
| PostgreSQL | `dwh` | Postgres 16 | Datos limpios, resúmenes, alertas |
| API + IA | `api` | FastAPI + **Gemini** (`GEMINI_API_KEY`) | REST protegida con login (token firmado) + `/api/chat` |
| Front + Auth (80/443) | `frontend` | React + Vite + Tailwind servido por nginx | Login sencillo (`FRONT_USER`/`FRONT_PASSWORD`), estado, alertas, chat |
| (lazo inferior) | ETL → Orion | HTTP | La alerta se publica como entidad `PlantAlert` |

**Decisiones**
- **Orion NGSI v2, no Orion-LD:** QuantumLeap consume notificaciones v2 y los ejemplos de `doc/` usan `/v2`. El compose original usaba `orion-ld` con comandos v2; se corrigió.
- **Dos almacenes a propósito:** CrateDB = crudo/series de tiempo; Postgres = DWH limpio para la API y la IA (la IA nunca lee datos sucios).
- **Front y API bajo el mismo origen** (nginx hace proxy de `/api/`), así no hay CORS ni se expone el 8000.

## 3. Modelo de datos

Entidad Orion por planta: `id=planta01`, `type=PlantSensor`, atributos `temperature`, `humidity`, `luminosity` (lux), `soilMoisture` (%), `location` (GPS).
Service `openiot` → QuantumLeap la guarda en `mtopeniot.etplantsensor`.

DWH (`app/dwh/init.sql`): `lectura_limpia`, `resumen_horario`, `alerta (warning|error)`.

Reglas del ETL (`app/etl/etl.py`, editar umbrales por cultivo):
- **Error:** valor fuera de rango físico (p. ej. T > 60 °C) o ausente → se guarda NULL + alerta `error`.
- **Warning:** valor válido pero fuera del rango agronómico.

## 4. Seguridad de red (EC2 t3.large)

Security Group: **22**, **4200** y **3000** (según `admin_cidr`; mejor solo tu IP), **80/443** (público), **1036** (Orion) y **7896** (agente, donde publica el sensor).
Internos sin publicar: Mongo, QuantumLeap, API. Postgres DWH solo en `127.0.0.1:5432` de la EC2 (acceso por túnel SSH, p. ej. DataGrip).
La EC2 tiene **IP elástica** (Terraform): no cambia al reiniciar ni al recrear la instancia.

**Conflicto resuelto:** CrateDB expone 5432 (wire protocol Postgres), igual que el DWH. Crate ya no publica 5432 y el DWH es solo interno.

**Recursos:** 8 GB RAM / 24 GB disco → Crate con heap 2 GB; vigilar disco (`docker system prune`, retención en Crate). Antes de levantar: `sudo sysctl -w vm.max_map_count=262144` (persistir en `/etc/sysctl.conf`).

## 5. Puesta en marcha

```bash
cp .env.example .env        # y cambiar las claves
docker compose up -d --build crate-db
bash doc/crate_auth.sh      # usuario "iot" de CrateDB
docker compose up -d --build
bash doc/provisionar.sh localhost
```
`doc/provisionar.sh` (idempotente) registra el grupo de servicio, el dispositivo `planta01` (con `apikey` y mapeo de atributos) y la suscripción Orion→QuantumLeap. Con Terraform todo esto lo hace el `user_data` al crear la instancia (ver `GUIA_DESPLIEGUE_AWS.md`).

## 6. Pendientes / por confirmar

1. **Contrato con el end device** (firmware en `firmware/IoT_Orion`): `POST :7896/iot/json?k=plantas2026&i=planta01` con las claves `temperatura_aire`, `humedad_aire`, `luz_lux`, `humedad_suelo_pct` (sin GPS). `doc/provisionar.sh` las mapea a `temperature`, `humidity`, `luminosity`, `soilMoisture`. Si el firmware cambia una clave, hay que cambiarla también ahí.
2. **Transporte:** si el device usa LoRa, hace falta un gateway LoRa→HTTP hacia el agente; si usa WiFi, publica directo.
3. **Puerto "5555"** que aparece junto al Agente en la pizarra: confirmar con el profesor (aquí se usó 7896, el HTTP sur estándar del agente JSON).
5. **HTTPS (443):** certificado (Let's Encrypt / ALB) para el front.
7. Fuera de alcance por decisión del equipo: rama LoRa (ChirpStack/InfluxDB), Airflow/NiFi, Redis, MCP y módulo de Gestión de la pizarra. El end device y sus gateways son de otro equipo.
8. HTTPS y autenticación en Orion si pasa de demo.

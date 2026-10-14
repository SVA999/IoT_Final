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

## 2. Capas y mapeo a la pizarra

| Pizarra | Servicio | Tecnología | Notas |
|---|---|---|---|
| Montar sensor (I2C) | End device (fuera de alcance, lo hace otro equipo) | TTGO T-Beam + HDC1080 (T/H) + sensor de luz + humedad de suelo analógica | Solo definimos el contrato JSON de entrada (abajo) |
| Agente | `iot-agent` | `fiware/iotagent-json` | Traduce JSON del dispositivo a entidades NGSI |
| O + MongoDB | `orion`, `mongo-db` | `fiware/orion` (NGSI v2) | Estado actual de cada planta |
| QL | `quantumleap` | orchestracities/quantumleap | Suscripción Orion → serie de tiempo |
| CrateDB | `crate-db` | CrateDB | Histórico **crudo** |
| Limpiar / Analizar | `etl` | Python | Limpia rangos, calcula agregados y alertas |
| PostgreSQL | `dwh` | Postgres 16 | Datos limpios, resúmenes, alertas |
| API + IA | `api` | FastAPI + **Gemini** (`GEMINI_API_KEY`) | REST protegida con login (token firmado) + `/api/chat` |
| Front + Auth (80/443) | `frontend` | nginx + HTML/JS | Login sencillo (`FRONT_USER`/`FRONT_PASSWORD`), estado, alertas, chat |
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

Security Group: **22** (solo tu IP), **80/443** (público), **1036** (Orion; idealmente solo IP del gateway), **7896** (agente, solo gateway), **4200** y **3000** (solo tu IP, o cerrarlos en producción).
Internos sin publicar: Mongo, Postgres DWH, QuantumLeap, API.

**Conflicto resuelto:** CrateDB expone 5432 (wire protocol Postgres), igual que el DWH. Crate ya no publica 5432 y el DWH es solo interno.

**Recursos:** 8 GB RAM / 24 GB disco → Crate con heap 2 GB; vigilar disco (`docker system prune`, retención en Crate). Antes de levantar: `sudo sysctl -w vm.max_map_count=262144` (persistir en `/etc/sysctl.conf`).

## 5. Puesta en marcha

```bash
cp .env.example .env        # y cambiar DWH_PASSWORD
docker compose up -d --build
```
Luego ejecutar `doc/provisionar.sh` (grupo de servicio, dispositivo `planta01` y suscripción Orion→QuantumLeap; referencia: `doc/ejemplocomandos.txt`, usar `"type": "PlantSensor"`) y provisionar el dispositivo en el agente (`:4041`).
Todo esto está automatizado en `doc/provisionar.sh <IP>`.

## 6. Pendientes / por confirmar

1. **Contrato con el end device:** debe publicar JSON al agente (`POST :7896/iot/json?k=plantas2026&i=planta01`) con las claves `t`, `h`, `l`, `s`, `loc`. Confirmar con el otro equipo.
2. **Transporte:** si el device usa LoRa, hace falta un gateway LoRa→HTTP hacia el agente; si usa WiFi, publica directo.
3. **Puerto "5555"** que aparece junto al Agente en la pizarra: confirmar con el profesor (aquí se usó 7896, el HTTP sur estándar del agente JSON).
5. **HTTPS (443):** certificado (Let's Encrypt / ALB) para el front.
7. Fuera de alcance por decisión del equipo: rama LoRa (ChirpStack/InfluxDB), Airflow/NiFi, Redis, MCP y módulo de Gestión de la pizarra. El end device y sus gateways son de otro equipo.
8. HTTPS y autenticación en Orion si pasa de demo.

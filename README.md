# IoT_Final – Monitoreo de plantas

Plataforma IoT sobre **FIWARE** para monitorear una planta: un sensor (ESP32) mide temperatura, humedad del aire, luz y humedad del suelo; la nube guarda el dato crudo, lo limpia, genera alertas y lo muestra en un panel web con un asistente de IA (Gemini). Todo corre en **una EC2 de AWS** con Docker Compose y se despliega con **Terraform**.

## Arquitectura

```
 ┌────────────┐  HTTP POST JSON   ┌─────────────┐  NGSI v2   ┌────────────┐
 │ ESP32      │ ────────────────► │ Agente IoT  │ ─────────► │   Orion    │ ◄── Mongo (estado actual)
 │ + sensores │   :7896           │ (JSON)      │            │  (:1036)   │
 └────────────┘                   └─────────────┘            └─────┬──────┘
                                                                   │ suscripción (notificación)
                                                                   ▼
 ┌────────────────────┐   limpia / analiza   ┌──────────┐    ┌─────────────┐
 │ Postgres (DWH)     │ ◄─────────────────── │   ETL    │ ◄─ │ CrateDB     │ ◄─ QuantumLeap
 │ lecturas, resumen, │      cada 5 min      │ (Python) │    │ histórico   │    (:8668)
 │ alertas            │                      └────┬─────┘    │ crudo       │
 └─────────┬──────────┘                           │          └─────────────┘
           │                                      └─► alertas vuelven a Orion (entidad PlantAlert)
           ▼
 ┌──────────────┐  /api/*   ┌─────────────────────┐
 │ API FastAPI  │ ◄──────── │ Front React + nginx │ ◄── navegador (:80)
 │ + Gemini     │           └─────────────────────┘
 └──────────────┘                                          Grafana (:3000) lee Postgres y Crate (opcional)
```

### Qué hace cada pieza

| Servicio (contenedor) | Rol | Notas |
|---|---|---|
| **ESP32** (`firmware/IoT_Orion`) | Lee los sensores y envía un JSON cada ~30 s por WiFi | `POST :7896/iot/json?k=plantas2026&i=planta01` |
| **iot-agent** (`fiware/iotagent-json:3.4.0`) | Traduce el JSON del sensor a una entidad NGSI | Mapea `temperatura_aire` → `temperature`, etc. (ver `doc/provisionar.sh`) |
| **orion** + **db-mongo** | Guarda el **estado actual** de la planta (`planta01`, tipo `PlantSensor`) | API REST, sin interfaz web. Puerto externo 1036 |
| **fiware-quantumleap** | Recibe las notificaciones de Orion y las guarda como serie de tiempo | |
| **db-crate** (CrateDB 5.8) | Histórico **crudo**, tabla `mtopeniot.etplantsensor` | Con autenticación: usuario `iot` |
| **etl** (Python) | Cada 5 min lee Crate, **limpia** (rangos físicos) y **analiza** (umbrales) y escribe en Postgres; las alertas también se publican en Orion | `app/etl/etl.py` |
| **dwh-postgres** (Postgres 16) | Almacén de datos limpios: `lectura_limpia`, `resumen_horario`, `alerta` | Solo escucha en `127.0.0.1` de la EC2 |
| **api** (FastAPI) | Login con token, `/api/plantas`, `/api/alertas`, `/api/chat` (Gemini) | La IA solo ve datos ya limpios |
| **frontend** (React + Vite + Tailwind → nginx) | Panel: estado de la planta, alertas, chat con IA | nginx hace proxy de `/api/` a la API (mismo origen, sin CORS) |
| **grafana** | Dashboards opcionales para técnicos | |

**Por qué dos bases de datos:** Crate guarda todo el histórico crudo (series de tiempo); Postgres guarda solo datos limpios y agregados, que es lo único que leen la API y la IA.

**Qué se expone a internet** (Security Group): 80 y 443 (front), 1036 (Orion), 7896 (agente, donde publica el sensor). Los puertos 22 (SSH), 4200 (Crate) y 3000 (Grafana) se limitan con la variable `admin_cidr`. Mongo, Postgres, QuantumLeap y la API no se publican.

Más detalle y decisiones de diseño: [doc/ARQUITECTURA.md](doc/ARQUITECTURA.md).

## Estructura del repositorio

```
app/
  etl/        ETL Python (Crate -> limpiar -> analizar -> Postgres + alertas a Orion)
  dwh/        Esquema de Postgres (init.sql)
  api_ai/     API FastAPI + chat con Gemini
  frontend/   React + Vite + Tailwind (build multi-etapa -> nginx)
firmware/     Código del ESP32 (PlatformIO)
infra/        Terraform: EC2, Security Group, IP elástica y script de arranque (user_data)
doc/          Guía de despliegue, arquitectura, provisionar.sh, crate_auth.sh
docker-compose.yml   Todos los servicios
```

## Puesta en marcha

### En AWS con Terraform (recomendado)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # completar claves y repo_url
terraform init && terraform apply
terraform output                               # IP elástica fija, URLs, comando SSH
```

La instancia instala Docker, clona el repo, crea el usuario de Crate, levanta el compose y provisiona el agente. Cuando `sudo tail -f /var/log/plantas-bootstrap.log` muestre `BOOTSTRAP OK` (5–10 min), abre `http://<IP>`.
Pon esa IP en `URL_SERVIDOR` de `firmware/IoT_Orion/src/main.cpp` y flashea el ESP32 (la IP es fija: se hace una sola vez).

Paso a paso completo, actualizaciones, reconstrucción y solución de problemas: **[doc/GUIA_DESPLIEGUE_AWS.md](doc/GUIA_DESPLIEGUE_AWS.md)**.

### Local (desarrollo)

```bash
sudo sysctl -w vm.max_map_count=262144      # lo exige CrateDB
cp .env.example .env                        # editar las claves
docker compose up -d --build crate-db
bash doc/crate_auth.sh                      # crea el usuario "iot" de Crate
docker compose up -d --build
bash doc/provisionar.sh localhost           # grupo de servicio, dispositivo y suscripción
```

Front en `http://localhost` (usuario/clave `FRONT_USER`/`FRONT_PASSWORD` del `.env`).

## Operación diaria

| Quiero… | Comando |
|---|---|
| Actualizar el código en la EC2 | `cd /opt/IoT_Final && sudo git pull && sudo docker compose up -d --build` |
| Re-provisionar el agente (idempotente) | `sudo bash doc/provisionar.sh localhost` |
| Reconstruir solo la EC2 conservando la IP | `terraform apply -replace=aws_instance.plantas` (en `infra/`, tras `git push`) |
| Ver datos en Orion | `curl.exe http://<IP>:1036/v2/entities -H "fiware-service: openiot" -H "fiware-servicepath: /"` |
| Ver datos en Crate | `http://<IP>:4200` (usuario `iot`) → `SELECT * FROM mtopeniot.etplantsensor` |
| Conectar DataGrip a Postgres | Túnel SSH a la EC2 y host `127.0.0.1:5432` (ver la guía, sección C) |

## Contrato con el sensor

El ESP32 envía un JSON con estas claves (deben coincidir con el mapeo de `doc/provisionar.sh`):

```json
{"temperatura_aire": 24.5, "humedad_aire": 60, "luz_lux": 15000, "humedad_suelo_pct": 45,
 "humedad_suelo_raw": 2100, "alerta_seco": false}
```

En Orion quedan como `temperature`, `humidity`, `luminosity` y `soilMoisture` (tipo `Number`) de la entidad `planta01`.

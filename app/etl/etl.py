"""ETL (una pasada): CrateDB (crudo) -> limpiar -> analizar -> Postgres (DWH) -> modelo predictivo -> avisos.

No es un proceso infinito: procesa lo pendiente, termina y devuelve un codigo de salida (0 = ok, 1 = error).
Quien lo dispara:
  - EVENTOS (camino principal): una suscripcion de Orion avisa al servicio `processor` (worker.py) cada vez que
    llega una lectura, y este llama a run().
  - cron cada 30 min (red de seguridad): recupera lo que se perdio si el procesador estuvo caido. Misma funcion.
  - a mano: docker compose run --rm etl
Es idempotente y seguro ante ejecuciones simultaneas (candado de Postgres): se puede lanzar las veces que se quiera.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import psycopg
import requests

import notify
import predict
from config import VALID, WARN

CRATE_URL = os.environ["CRATE_URL"]
TABLE = os.environ["CRATE_TABLE"]
DSN = os.environ["DWH_DSN"]
ORION = os.environ["ORION_URL"]
CRATE_AUTH = (os.environ.get("CRATE_USER", "iot"), os.environ.get("CRATE_PASSWORD", ""))
SCHEMA_FILE = os.environ.get("SCHEMA_FILE", "/app/schema.sql")
BATCH = int(os.environ.get("ETL_BATCH", "5000"))
MAX_BATCHES = int(os.environ.get("ETL_MAX_BATCHES", "100"))   # tope de seguridad: el trabajo siempre termina
REWIND_S = int(os.environ.get("ETL_REWIND_S", "120"))         # relee los ultimos segundos por si Crate llego tarde con una lectura
ALERT_COOLDOWN_MIN = int(os.environ.get("ALERT_COOLDOWN_MIN", "30"))  # no repite la misma alerta dentro de este plazo
LOCK_ID = 727001                                              # candado de Postgres: una sola corrida a la vez


def extract(since_ms):
    q = (f"SELECT entity_id, time_index, temperature, humidity, luminosity, soilmoisture "
         f"FROM {TABLE} WHERE time_index > ? ORDER BY time_index LIMIT {BATCH}")
    r = requests.post(CRATE_URL, json={"stmt": q, "args": [since_ms]}, auth=CRATE_AUTH, timeout=30)
    if r.status_code == 404:  # la tabla aun no existe: el sensor todavia no ha enviado nada
        return []
    r.raise_for_status()
    return r.json()["rows"]


def clean(rows):
    out = []
    for eid, ts, t, h, lx, s in rows:
        vals = {"temperature": t, "humidity": h, "luminosity": lx, "soil_moisture": s}
        for k, v in vals.items():  # fuera de rango fisico -> nulo (error de sensor); nunca se rellena con un valor inventado
            if v is not None and not VALID[k][0] <= v <= VALID[k][1]:
                vals[k] = None
        out.append((eid, ts, vals))
    return out


def alerta_de(k, v):
    if v is None:
        return "error", f"{k}_invalido", f"Lectura de {k} invalida o ausente"
    if not WARN[k][0] <= v <= WARN[k][1]:
        return "warning", f"{k}_fuera_rango", f"{k}={v} fuera de {WARN[k]}"
    return None


def load(cur, rows):
    """Guarda lecturas, alertas y resumen horario de un lote. Devuelve las alertas NUEVAS y recientes."""
    cur.executemany(
        "INSERT INTO lectura_limpia(entity_id, ts, temperature, humidity, luminosity, soil_moisture) "
        "VALUES (%s, to_timestamp(%s/1000.0), %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        [(e, ts, v["temperature"], v["humidity"], v["luminosity"], v["soil_moisture"]) for e, ts, v in rows])

    ahora_ms = time.time() * 1000
    nuevas = []
    for eid, ts, vals in rows:
        for k, v in vals.items():
            a = alerta_de(k, v)
            if a is None:
                continue
            sev, tipo, msg = a
            # Una alerta por condicion, no una por lectura: se omite si ya hubo una igual hace poco
            cur.execute(
                "INSERT INTO alerta(entity_id, ts, severidad, tipo, mensaje) "
                "SELECT %(e)s::text, to_timestamp(%(t)s/1000.0), %(s)s::text, %(k)s::text, %(m)s::text "
                "WHERE NOT EXISTS (SELECT 1 FROM alerta WHERE entity_id = %(e)s::text AND tipo = %(k)s::text "
                "  AND ts BETWEEN to_timestamp(%(t)s/1000.0) - make_interval(mins => %(c)s) "
                "             AND to_timestamp(%(t)s/1000.0)) "
                "ON CONFLICT DO NOTHING RETURNING id",
                {"e": eid, "t": ts, "s": sev, "k": tipo, "m": msg, "c": ALERT_COOLDOWN_MIN})
            fila = cur.fetchone()
            # Solo se avisa de lo reciente: al ponerse al dia tras una caida no se inundan los chats con historia vieja
            if not fila or ahora_ms - ts > notify.MAX_EDAD_MIN * 60000:
                continue
            nuevas.append((eid, sev, msg))
            ev = {"type": "alerta", "id": fila[0], "entity_id": eid, "severidad": sev, "mensaje": msg, "tipo": tipo}
            cur.execute("SELECT pg_notify('eventos', %s)", (json.dumps(ev),))   # -> websocket del navegador
            if not notify.ignorada(tipo):                                        # -> Telegram (bandeja de salida)
                icono = "🛑" if sev == "error" else "⚠️"
                notify.encolar(cur, "alerta", fila[0], f"{eid}|{tipo}", sev,
                               f"{icono} Alerta ({sev}) — {eid}", f"{msg}\n{notify.hora_local(datetime.fromtimestamp(ts / 1000, tz=timezone.utc))}")

    # Resumen horario de todas las horas tocadas por el lote (no solo las ultimas)
    cur.execute(
        "INSERT INTO resumen_horario "
        "SELECT entity_id, date_trunc('hour', ts), avg(temperature), min(temperature), max(temperature), "
        "       avg(humidity), avg(luminosity), avg(soil_moisture), count(*) "
        "FROM lectura_limpia WHERE ts >= date_trunc('hour', to_timestamp(%s/1000.0)) GROUP BY 1, 2 "
        "ON CONFLICT (entity_id, hora) DO UPDATE SET temp_avg = EXCLUDED.temp_avg, temp_min = EXCLUDED.temp_min, "
        "  temp_max = EXCLUDED.temp_max, hum_avg = EXCLUDED.hum_avg, lux_avg = EXCLUDED.lux_avg, "
        "  soil_avg = EXCLUDED.soil_avg, n = EXCLUDED.n",
        (rows[0][1],))
    return nuevas


# Orion rechaza estos caracteres en valores de atributos ("Invalid characters in attribute value")
_ORION_PROHIBIDOS = re.compile(r"[<>\"'=;()]")


def notify_orion(alertas):
    """Lazo de retorno de la pizarra: la alerta vuelve a Orion como entidad. Un fallo aqui no invalida el ETL."""
    for eid, sev, msg in alertas[-20:]:
        try:
            requests.post(f"{ORION}/v2/entities?options=upsert", timeout=10, json={
                "id": f"alert:{eid}", "type": "PlantAlert",
                "severity": {"type": "Text", "value": sev},
                "message": {"type": "Text", "value": _ORION_PROHIBIDOS.sub(" ", msg)},
                "refPlant": {"type": "Text", "value": eid}}).raise_for_status()
        except requests.RequestException as e:
            print(f"AVISO: no se pudo publicar la alerta en Orion: {e.__class__.__name__}", flush=True)
            return


def _evento(conn, payload):
    conn.execute("SELECT pg_notify('eventos', %s)", (json.dumps(payload),))


def run():
    """Una pasada completa. Devuelve un resumen (dict), o None si ya habia otra corrida en curso."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        if not conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,)).fetchone()[0]:
            return None   # otra corrida (cron o evento) esta trabajando: ella cubre lo pendiente
        with open(SCHEMA_FILE, encoding="utf-8") as f:  # esquema unico (app/dwh/init.sql); idempotente
            conn.execute(f.read())

        since = conn.execute(
            "SELECT coalesce(max(extract(epoch FROM ts)) * 1000, 0)::bigint FROM lectura_limpia").fetchone()[0]
        since = max(0, since - REWIND_S * 1000)
        total_antes = conn.execute("SELECT count(*) FROM lectura_limpia").fetchone()[0]

        alertas = []
        for _ in range(MAX_BATCHES):  # ponerse al dia aunque haya mucho atraso, con tope
            rows = clean(extract(since))
            if not rows:
                break
            with conn.transaction():  # lecturas + alertas + resumen + avisos encolados: todo o nada
                alertas += load(conn.cursor(), rows)
            since = rows[-1][1]
            if len(rows) < BATCH:
                break
        nuevas_lecturas = conn.execute("SELECT count(*) FROM lectura_limpia").fetchone()[0] - total_antes

        with conn.transaction():
            preds = predict.predecir(conn)

        if nuevas_lecturas > 0:
            _evento(conn, {"type": "lecturas", "n": nuevas_lecturas})   # el navegador refresca sin sondear
        if nuevas_lecturas > 0 or preds:
            _evento(conn, {"type": "modelo"})

        enviadas = notify.despachar(conn)
    notify_orion(alertas)
    return {"lecturas": nuevas_lecturas, "alertas": len(alertas), "predicciones": len(preds), "telegram": enviadas}


def main():
    r = run()
    if r is None:
        print("ETL omitido: hay otra corrida en curso", flush=True)
        return
    print(f"ETL ok: {r['lecturas']} lecturas, {r['alertas']} alertas nuevas, {r['predicciones']} predicciones nuevas, "
          f"{r['telegram']} avisos a Telegram", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ETL FALLO: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

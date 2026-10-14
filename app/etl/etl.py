"""ETL: CrateDB (crudo) -> limpiar -> analizar -> Postgres (DWH) + alertas a Orion."""
import os
import time

import psycopg
import requests

CRATE_URL = os.environ["CRATE_URL"]
TABLE = os.environ["CRATE_TABLE"]
DSN = os.environ["DWH_DSN"]
ORION = os.environ["ORION_URL"]
INTERVAL = int(os.environ.get("ETL_INTERVAL_SECONDS", "300"))

# Rangos fisicos validos (limpiar) y umbrales de advertencia (analizar). Ajustar al cultivo.
VALID = {"temperature": (-10, 60), "humidity": (0, 100), "luminosity": (0, 120000), "soil_moisture": (0, 100)}
WARN = {"temperature": (10, 35), "humidity": (30, 90), "luminosity": (1000, 80000), "soil_moisture": (20, 80)}


def extract(since):
    q = (f"SELECT entity_id, time_index, temperature, humidity, luminosity, soilmoisture "
         f"FROM {TABLE} WHERE time_index > ? ORDER BY time_index LIMIT 5000")
    r = requests.post(CRATE_URL, json={"stmt": q, "args": [since]}, timeout=30)
    r.raise_for_status()
    return r.json()["rows"]


def clean(rows):
    out = []
    for eid, ts, t, h, lx, s in rows:
        vals = {"temperature": t, "humidity": h, "luminosity": lx, "soil_moisture": s}
        for k, v in vals.items():  # fuera de rango fisico -> nulo (error de sensor)
            if v is not None and not VALID[k][0] <= v <= VALID[k][1]:
                vals[k] = None
        out.append((eid, ts, vals))
    return out


def analyze(rows):
    alerts = []
    for eid, ts, vals in rows:
        for k, v in vals.items():
            if v is None:
                alerts.append((eid, ts, "error", f"{k}_invalido", f"Lectura de {k} invalida o ausente"))
            elif not WARN[k][0] <= v <= WARN[k][1]:
                alerts.append((eid, ts, "warning", f"{k}_fuera_rango", f"{k}={v} fuera de {WARN[k]}"))
    return alerts


def load(cur, rows, alerts):
    for eid, ts, v in rows:
        cur.execute(
            "INSERT INTO lectura_limpia(entity_id, ts, temperature, humidity, luminosity, soil_moisture) "
            "VALUES (%s, to_timestamp(%s/1000.0), %s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (eid, ts, v["temperature"], v["humidity"], v["luminosity"], v["soil_moisture"]))
    for eid, ts, sev, tipo, msg in alerts:
        cur.execute(
            "INSERT INTO alerta(entity_id, ts, severidad, tipo, mensaje) "
            "VALUES (%s, to_timestamp(%s/1000.0), %s, %s, %s) ON CONFLICT DO NOTHING",
            (eid, ts, sev, tipo, msg))
    cur.execute("""
        INSERT INTO resumen_horario
        SELECT entity_id, date_trunc('hour', ts), avg(temperature), min(temperature), max(temperature),
               avg(humidity), avg(luminosity), avg(soil_moisture), count(*)
        FROM lectura_limpia WHERE ts > now() - interval '2 hours' GROUP BY 1, 2
        ON CONFLICT (entity_id, hora) DO UPDATE SET temp_avg=EXCLUDED.temp_avg, temp_min=EXCLUDED.temp_min,
          temp_max=EXCLUDED.temp_max, hum_avg=EXCLUDED.hum_avg, lux_avg=EXCLUDED.lux_avg, soil_avg=EXCLUDED.soil_avg, n=EXCLUDED.n""")


def notify_orion(alerts):
    """Lazo de retorno de la pizarra: la alerta vuelve a Orion como entidad."""
    for eid, _ts, sev, _tipo, msg in alerts[-20:]:
        requests.post(f"{ORION}/v2/entities?options=upsert", timeout=10, json={
            "id": f"alert:{eid}", "type": "PlantAlert",
            "severity": {"type": "Text", "value": sev},
            "message": {"type": "Text", "value": msg},
            "refPlant": {"type": "Text", "value": eid}})


def main():
    with psycopg.connect(DSN, autocommit=True) as conn:
        while True:
            try:
                cur = conn.cursor()
                cur.execute("SELECT coalesce(max(extract(epoch FROM ts))*1000, 0)::bigint FROM lectura_limpia")
                since = cur.fetchone()[0]
                rows = clean(extract(since))
                alerts = analyze(rows)
                load(cur, rows, alerts)
                notify_orion(alerts)
                print(f"ETL ok: {len(rows)} lecturas, {len(alerts)} alertas", flush=True)
            except Exception as e:  # el ciclo nunca debe morir
                print("ETL error:", e, flush=True)
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()

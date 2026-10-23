"""Procesador de eventos: recibe las notificaciones de la suscripcion de Orion y dispara el ETL en vivo.

Flujo:  sensor -> agente IoT -> Orion --(suscripcion)--> POST /orion/notify  -> run() del ETL
Cada lectura nueva genera un evento; las rafagas se agrupan (EVENT_DEBOUNCE_S) y se da tiempo a QuantumLeap de
escribir en Crate antes de leerlo. NO sondea: mientras no llegan eventos el servicio esta dormido (await), sin
consumir CPU ni consultar nada. Si una corrida falla no reintenta en bucle: la siguiente lectura o el cron de
seguridad (cada 30 min) la recuperan.
"""
import asyncio
import contextlib
import os
import time

from fastapi import FastAPI

import etl

DEBOUNCE_S = float(os.environ.get("EVENT_DEBOUNCE_S", "8"))
REINTENTO_OCUPADO_S = 15      # si otra corrida (cron) tiene el candado, se vuelve a intentar una vez despues

hay_evento = asyncio.Event()
estado = {"eventos_recibidos": 0, "ultimo_evento": None, "ultima_corrida": None, "ultimo_error": None}


async def trabajador():
    while True:  # espera por eventos (await): dormido mientras no haya notificaciones
        await hay_evento.wait()
        await asyncio.sleep(DEBOUNCE_S)   # agrupa la rafaga y da tiempo a QuantumLeap -> Crate
        hay_evento.clear()
        try:
            r = await asyncio.to_thread(etl.run)
        except Exception as e:
            estado["ultimo_error"] = f"{e.__class__.__name__}: {e}"
            print(f"ETL por evento FALLO: {estado['ultimo_error']}", flush=True)
            continue
        if r is None:                      # otra corrida en curso: reintenta una sola vez
            await asyncio.sleep(REINTENTO_OCUPADO_S)
            hay_evento.set()
            continue
        estado["ultima_corrida"] = {**r, "cuando": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        estado["ultimo_error"] = None
        print(f"ETL por evento ok: {r}", flush=True)


@contextlib.asynccontextmanager
async def lifespan(_app):
    tarea = asyncio.create_task(trabajador())
    yield
    tarea.cancel()


app = FastAPI(title="Procesador de eventos", lifespan=lifespan)


@app.post("/orion/notify")
async def orion_notify():
    """Orion llama aqui en cada actualizacion de PlantSensor. Responde de inmediato; el trabajo va aparte."""
    estado["eventos_recibidos"] += 1
    estado["ultimo_evento"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    hay_evento.set()
    return {"ok": True}


@app.get("/estado")
async def get_estado():
    return estado

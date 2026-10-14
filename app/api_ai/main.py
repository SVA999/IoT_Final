"""API: lee el DWH y expone plantas/alertas + chat con IA (proveedor aun sin definir)."""
import os

import psycopg
from fastapi import FastAPI
from psycopg.rows import dict_row
from pydantic import BaseModel

DSN = os.environ["DWH_DSN"]
app = FastAPI(title="Plantas API")


def q(sql, *args):
    with psycopg.connect(DSN, row_factory=dict_row) as c:
        return c.execute(sql, args).fetchall()


@app.get("/api/plantas")
def plantas():
    return q("SELECT DISTINCT ON (entity_id) * FROM lectura_limpia ORDER BY entity_id, ts DESC")


@app.get("/api/plantas/{pid}/historial")
def historial(pid: str, horas: int = 24):
    return q("SELECT * FROM resumen_horario WHERE entity_id=%s "
             "AND hora > now() - make_interval(hours => %s) ORDER BY hora", pid, horas)


@app.get("/api/alertas")
def alertas(limit: int = 50):
    return q("SELECT * FROM alerta ORDER BY ts DESC LIMIT %s", limit)


class Pregunta(BaseModel):
    pregunta: str
    planta: str | None = None


def ask_llm(prompt: str) -> str:
    """Punto de extension: implementar el proveedor elegido (AI_PROVIDER/AI_API_KEY/AI_MODEL)."""
    if os.environ.get("AI_PROVIDER", "none") == "none":
        return "IA no configurada todavia. Contexto que se enviaria:\n\n" + prompt
    raise NotImplementedError("Proveedor de IA pendiente de definir")


@app.post("/api/chat")
def chat(p: Pregunta):
    ctx = {"ultimas": plantas(), "alertas": alertas(20)}
    prompt = (f"Eres un asistente agronomo. Datos del DWH: {ctx}\n"
              f"Planta: {p.planta or 'todas'}\nPregunta: {p.pregunta}")
    return {"respuesta": ask_llm(prompt)}

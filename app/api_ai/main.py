"""API: lee el DWH y expone plantas/alertas + chat con Gemini. Login sencillo con token firmado."""
import base64
import hashlib
import hmac
import os
import time

import httpx
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel

DSN = os.environ["DWH_DSN"]
FRONT_USER = os.environ["FRONT_USER"]
FRONT_PASSWORD = os.environ["FRONT_PASSWORD"]
AUTH_SECRET = os.environ["AUTH_SECRET"].encode()
TOKEN_TTL = 8 * 3600
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

app = FastAPI(title="Plantas API")


# ---------- Autenticacion ----------
def _sign(payload: str) -> str:
    return hmac.new(AUTH_SECRET, payload.encode(), hashlib.sha256).hexdigest()


def make_token(user: str) -> str:
    payload = f"{user}:{int(time.time()) + TOKEN_TTL}"
    return base64.urlsafe_b64encode(f"{payload}:{_sign(payload)}".encode()).decode()


def require_auth(authorization: str = Header(default="")):
    try:
        raw = base64.urlsafe_b64decode(authorization.removeprefix("Bearer ").encode()).decode()
        user, exp, sig = raw.rsplit(":", 2)
        ok = hmac.compare_digest(sig, _sign(f"{user}:{exp}")) and int(exp) > time.time()
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(status_code=401, detail="No autenticado")


class Login(BaseModel):
    usuario: str
    password: str


@app.post("/api/login")
def login(b: Login):
    ok_user = hmac.compare_digest(b.usuario, FRONT_USER)
    ok_pass = hmac.compare_digest(b.password, FRONT_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    return {"token": make_token(b.usuario)}


# ---------- Datos ----------
def q(sql, *args):
    with psycopg.connect(DSN, row_factory=dict_row) as c:
        return c.execute(sql, args).fetchall()


@app.get("/api/plantas", dependencies=[Depends(require_auth)])
def plantas():
    return q("SELECT DISTINCT ON (entity_id) * FROM lectura_limpia ORDER BY entity_id, ts DESC")


@app.get("/api/plantas/{pid}/historial", dependencies=[Depends(require_auth)])
def historial(pid: str, horas: int = 24):
    return q("SELECT * FROM resumen_horario WHERE entity_id=%s "
             "AND hora > now() - make_interval(hours => %s) ORDER BY hora", pid, horas)


@app.get("/api/alertas", dependencies=[Depends(require_auth)])
def alertas(limit: int = 50):
    return q("SELECT * FROM alerta ORDER BY ts DESC LIMIT %s", limit)


# ---------- IA (Gemini) ----------
class Pregunta(BaseModel):
    pregunta: str
    planta: str | None = None


def ask_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY no configurada")
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": GEMINI_API_KEY},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Gemini respondio {r.status_code}")
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


@app.post("/api/chat", dependencies=[Depends(require_auth)])
def chat(p: Pregunta):
    ctx = {"ultimas_lecturas": plantas(), "alertas_recientes": alertas(20)}
    prompt = ("Eres un asistente agronomo. Responde en español, breve y accionable, usando solo "
              f"estos datos del sistema de monitoreo: {ctx}\n"
              f"Planta: {p.planta or 'todas'}\nPregunta: {p.pregunta}")
    return {"respuesta": ask_gemini(prompt)}

"""API: lee el DWH y expone plantas/alertas + chat con Gemini. Login sencillo con token firmado."""
import asyncio
import base64
import contextlib
import hashlib
import hmac
import os
import time

import httpx
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from psycopg.rows import dict_row
from pydantic import BaseModel

DSN = os.environ["DWH_DSN"]
FRONT_USER = os.environ["FRONT_USER"]
FRONT_PASSWORD = os.environ["FRONT_PASSWORD"]
AUTH_SECRET = os.environ["AUTH_SECRET"].encode()
TOKEN_TTL = 8 * 3600
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

clientes: set[WebSocket] = set()   # navegadores conectados al websocket de notificaciones


async def difundir(texto: str):
    """Envia una notificacion a todos los navegadores conectados; descarta los que ya no responden."""
    for ws in list(clientes):
        try:
            await ws.send_text(texto)
        except Exception:
            clientes.discard(ws)


async def escuchar_predicciones():
    """El ETL hace pg_notify('eventos', ...) (lecturas, alertas, predicciones, modelo); aqui se recibe y se empuja por websocket.
    Es por eventos (sin sondeo). Si se cae la conexion, reintenta con espera creciente (1 s ... 30 s)."""
    espera = 1
    while True:
        try:
            async with await psycopg.AsyncConnection.connect(DSN, autocommit=True) as conn:
                await conn.execute("LISTEN eventos")
                espera = 1
                async for n in conn.notifies():
                    await difundir(n.payload)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"LISTEN eventos: {e.__class__.__name__}: {e}; reintento en {espera}s", flush=True)
        await asyncio.sleep(espera)
        espera = min(espera * 2, 30)


@contextlib.asynccontextmanager
async def lifespan(_app):
    tarea = asyncio.create_task(escuchar_predicciones())
    yield
    tarea.cancel()


app = FastAPI(title="Plantas API", lifespan=lifespan)


# ---------- Autenticacion ----------
def _sign(payload: str) -> str:
    return hmac.new(AUTH_SECRET, payload.encode(), hashlib.sha256).hexdigest()


def make_token(user: str) -> str:
    payload = f"{user}:{int(time.time()) + TOKEN_TTL}"
    return base64.urlsafe_b64encode(f"{payload}:{_sign(payload)}".encode()).decode()


def token_valido(token: str) -> bool:
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        user, exp, sig = raw.rsplit(":", 2)
        return hmac.compare_digest(sig, _sign(f"{user}:{exp}")) and int(exp) > time.time()
    except Exception:
        return False


def require_auth(authorization: str = Header(default="")):
    if not token_valido(authorization.removeprefix("Bearer ")):
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


@app.get("/api/salud")
def salud():
    """Sin login. Sirve para comprobar que el sistema corre y QUE VERSION: version = commit desplegado por Terraform."""
    try:
        q("SELECT 1")
        db = True
    except psycopg.Error:
        db = False
    return {"ok": db, "version": os.environ.get("DEPLOY_ID", "") or "local"}


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


@app.get("/api/predicciones", dependencies=[Depends(require_auth)])
def predicciones(horas: int = 24, limit: int = 20):
    """Predicciones recientes del modelo de tendencia (solo las generadas a partir de lecturas reales)."""
    return q("SELECT * FROM prediccion "
             "WHERE generado > now() - make_interval(hours => %s) ORDER BY generado DESC LIMIT %s", horas, limit)


@app.get("/api/modelo/estado", dependencies=[Depends(require_auth)])
def modelo_estado(planta: str | None = None):
    """Estado actual del modelo por planta y variable (incluye POR QUE no predice cuando no lo hace)."""
    return q("SELECT * FROM modelo_estado WHERE (%s::text IS NULL OR entity_id = %s::text) ORDER BY entity_id, variable",
             planta, planta)


@app.get("/api/plantas/{pid}/lecturas", dependencies=[Depends(require_auth)])
def lecturas(pid: str, horas: int = 8):
    """Lecturas reales (ya limpias) para graficar la tendencia."""
    return q("SELECT ts, temperature, humidity, luminosity, soil_moisture FROM lectura_limpia "
             "WHERE entity_id = %s AND ts > now() - make_interval(hours => %s) ORDER BY ts LIMIT 3000", pid, horas)


@app.get("/api/notificaciones", dependencies=[Depends(require_auth)])
def notificaciones(limit: int = 20):
    """Bandeja de salida de avisos externos (Telegram) y su estado."""
    return q("SELECT id, origen, severidad, titulo, mensaje, creada, enviada, estado, detalle "
             "FROM notificacion ORDER BY id DESC LIMIT %s", limit)


@app.websocket("/api/ws")
async def ws_notificaciones(ws: WebSocket):
    """Notificaciones en vivo. El navegador envia el token como PRIMER mensaje (no va en la URL ni en logs)."""
    await ws.accept()
    try:
        if not token_valido(await asyncio.wait_for(ws.receive_text(), timeout=5)):
            raise ValueError("token invalido")
    except Exception:
        await ws.close(code=4401)
        return
    clientes.add(ws)
    try:
        await ws.send_text('{"type":"ready"}')
        while True:
            if await ws.receive_text() == "ping":   # latido del cliente: mantiene viva la conexion tras nginx
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        clientes.discard(ws)


# ---------- IA (Gemini) ----------
class Pregunta(BaseModel):
    pregunta: str
    planta: str | None = None


def ask_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY no configurada")
    try:
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=504, detail=f"No se pudo contactar a Gemini: {e.__class__.__name__}")
    if r.status_code != 200:
        try:  # mensaje de Google (p. ej. modelo inexistente, clave invalida, cuota): util para diagnosticar
            motivo = r.json()["error"]["message"]
        except (KeyError, TypeError, ValueError):
            motivo = r.text[:200]
        print(f"Gemini {GEMINI_MODEL} -> {r.status_code}: {motivo}", flush=True)
        raise HTTPException(status_code=502, detail=f"Gemini ({GEMINI_MODEL}) respondio {r.status_code}: {motivo}"[:300])
    try:
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts) or "La IA no genero respuesta."
    except (KeyError, IndexError, TypeError, ValueError):
        # p. ej. respuesta bloqueada por filtros de seguridad: no trae 'candidates'
        raise HTTPException(status_code=502, detail="Gemini devolvio una respuesta sin contenido")


@app.post("/api/chat", dependencies=[Depends(require_auth)])
def chat(p: Pregunta):
    try:
        ctx = {"ultimas_lecturas": plantas(), "alertas_recientes": alertas(20)}
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Base de datos no disponible")
    prompt = ("Eres un asistente agronomo. Responde en español, breve y accionable, usando solo "
              f"estos datos del sistema de monitoreo: {ctx}\n"
              f"Planta: {p.planta or 'todas'}\nPregunta: {p.pregunta}")
    return {"respuesta": ask_gemini(prompt)}

"""Notificaciones externas por Telegram (bandeja de salida + despachador).

Por que Telegram: es gratis, se configura en 2 minutos con @BotFather, no necesita dominio, servidor SMTP ni
aprobacion de plantillas (WhatsApp Business exige verificar la empresa y aprobar mensajes), y es una sola llamada HTTPS.

Cada alerta/prediccion nueva se ENCOLA en `notificacion` (dentro de la misma transaccion que la crea) y `despachar`
la envia despues. Garantias: no se pierde un aviso si Telegram falla (reintenta, maximo MAX_INTENTOS), no se repite el
mismo aviso dentro de COOLDOWN_MIN, y el token nunca se escribe en los logs.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHATS = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()]
API_BASE = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")
COOLDOWN_MIN = int(os.environ.get("NOTIFY_COOLDOWN_MIN", "120"))      # no repite el mismo aviso en este plazo
MAX_INTENTOS = int(os.environ.get("NOTIFY_MAX_INTENTOS", "5"))
MAX_EDAD_MIN = int(os.environ.get("NOTIFY_MAX_AGE_MIN", "60"))        # no avisa de lecturas viejas (p. ej. al ponerse al dia)
# Variables cuyas ALERTAS no se envian a Telegram. La luz baja de noche es normal y llenaria el chat de avisos.
IGNORAR = [v.strip() for v in os.environ.get("NOTIFY_IGNORE_VARS", "luminosity").split(",") if v.strip()]
TZ = ZoneInfo(os.environ.get("TIMEZONE", "America/Bogota"))


def hay_canal():
    return bool(TOKEN and CHATS)


def hora_local(dt):
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.astimezone(TZ).strftime("%d/%m %H:%M")


def ignorada(tipo):
    return any(tipo.startswith(v + "_") for v in IGNORAR)


def encolar(db, origen, origen_id, clave, severidad, titulo, mensaje):
    """db = conexion o cursor de psycopg. Se llama dentro de la transaccion que crea la alerta/prediccion."""
    db.execute(
        "INSERT INTO notificacion(origen, origen_id, clave, severidad, titulo, mensaje) "
        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (origen, origen_id, clave, severidad, titulo, mensaje))


def enviar_telegram(texto):
    """Devuelve (ok, detalle). ok=True si al menos un chat lo recibio. Nunca incluye el token en el detalle."""
    fallos, enviados = [], 0
    for chat in CHATS:
        try:
            r = requests.post(f"{API_BASE}/bot{TOKEN}/sendMessage", timeout=10,
                              json={"chat_id": chat, "text": texto, "disable_web_page_preview": True})
        except requests.RequestException as e:   # solo el tipo de error: el mensaje de requests incluye la URL con el token
            fallos.append(f"{chat}: {e.__class__.__name__}")
            continue
        if r.status_code == 200:
            enviados += 1
        else:
            try:
                motivo = r.json().get("description", "")
            except ValueError:
                motivo = ""
            fallos.append(f"{chat}: HTTP {r.status_code} {motivo}".strip())
    return enviados > 0, "; ".join(fallos) or None


def despachar(conn):
    """Envia las notificaciones pendientes. Devuelve cuantas se enviaron. Un fallo aqui no invalida el ETL."""
    pend = conn.execute(
        "SELECT id, clave, titulo, mensaje, intentos FROM notificacion WHERE estado = 'pendiente' ORDER BY id LIMIT 50"
    ).fetchall()
    if not pend:
        return 0
    if not hay_canal():
        conn.execute("UPDATE notificacion SET estado = 'sin_canal', detalle = 'Telegram no configurado' "
                     "WHERE estado = 'pendiente'")
        return 0
    enviadas = 0
    for nid, clave, titulo, mensaje, intentos in pend:
        repetida = conn.execute(
            "SELECT 1 FROM notificacion WHERE clave = %s AND estado = 'enviada' "
            "AND enviada > now() - make_interval(mins => %s)", (clave, COOLDOWN_MIN)).fetchone()
        if repetida:
            conn.execute("UPDATE notificacion SET estado = 'suprimida', "
                         "detalle = 'ya se aviso lo mismo hace menos de ' || %s || ' min' WHERE id = %s",
                         (COOLDOWN_MIN, nid))
            continue
        ok, detalle = enviar_telegram(f"{titulo}\n{mensaje}")
        if ok:
            conn.execute("UPDATE notificacion SET estado = 'enviada', enviada = now(), detalle = %s, "
                         "intentos = intentos + 1 WHERE id = %s", (detalle, nid))
            enviadas += 1
        else:
            fallida = intentos + 1 >= MAX_INTENTOS
            conn.execute("UPDATE notificacion SET intentos = intentos + 1, detalle = %s, estado = %s WHERE id = %s",
                         (detalle, "fallida" if fallida else "pendiente", nid))
            print(f"AVISO: Telegram no entrego la notificacion {nid} (intento {intentos + 1}/{MAX_INTENTOS}): {detalle}",
                  flush=True)
    return enviadas

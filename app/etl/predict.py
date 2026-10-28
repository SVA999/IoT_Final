"""Modelo predictivo: tendencia lineal (minimos cuadrados) sobre lecturas REALES del sensor.

Para cada planta y variable ajusta una recta a la ventana reciente de lecturas limpias y estima cuando
cruzaria el limite agronomico (config.WARN). No usa datos sinteticos ni de relleno: sin evidencia suficiente NO predice
y lo dice (estado y detalle quedan en `modelo_estado`, que muestra la pantalla "Predicciones").

Estados por variable:
  pronostico          (temperatura y humedad del aire) valor esperado a +1, +3 y +6 h con margen de error; no genera avisos
  prediccion          cruzaria un limite dentro del horizonte (se avisa)
  sin_riesgo          hay tendencia hacia un limite, pero lo cruzaria mas alla del horizonte
  estable             se aleja de los limites (o no cambia)
  fuera_de_rango      ya esta fuera del rango: eso lo cubre la alerta normal
  datos_insuficientes pocas lecturas (tambien tras un cambio brusco, p. ej. un riego, que reinicia la ventana)
  sin_tendencia       las lecturas no varian
  ajuste_pobre        la recta no explica los datos (R2 bajo): no es confiable
  datos_viejos        el sensor no envia desde hace mucho
La luminosidad no se modela: es ciclica (dia/noche) y una recta no la representa.
"""
import json
import os

import notify
from config import WARN

# columna -> (etiqueta, unidad, salto entre lecturas consecutivas que reinicia la ventana)
VARIABLES = {
    "soil_moisture": ("Humedad del suelo", "%", 10.0),
    "temperature": ("Temperatura del aire", "°C", 5.0),
    "humidity": ("Humedad del aire", "%", 20.0),
}
TITULOS = {
    ("soil_moisture", "min"): "💧 Se va a acabar el agua del suelo",
    ("soil_moisture", "max"): "💧 Exceso de agua en el suelo",
    ("temperature", "min"): "🥶 Se prevé frío para la planta",
    ("temperature", "max"): "🌡️ Se prevé calor excesivo",
    ("humidity", "min"): "🏜️ El aire se va a poner demasiado seco",
    ("humidity", "max"): "💦 El aire se va a poner demasiado húmedo",
}

WINDOW_H = float(os.environ.get("PRED_WINDOW_H", "6"))         # ventana de lecturas a ajustar
HORIZON_H = float(os.environ.get("PRED_HORIZON_H", "6"))       # solo avisa si el cruce es dentro de este plazo
MIN_POINTS = int(os.environ.get("PRED_MIN_POINTS", "12"))
MIN_SPAN_H = float(os.environ.get("PRED_MIN_SPAN_H", "1"))
MIN_R2 = float(os.environ.get("PRED_MIN_R2", "0.6"))
MAX_STALE_MIN = float(os.environ.get("PRED_MAX_STALE_MIN", "30"))
COOLDOWN_H = float(os.environ.get("PRED_COOLDOWN_H", "3"))     # no repite el mismo aviso dentro de este plazo
TEMP_WINDOW_H = float(os.environ.get("PRED_TEMP_WINDOW_H", "2"))   # temperatura: ventana corta para pronosticar su valor
PRON_HORAS = (1.0, 3.0, 6.0)                                   # temperatura: dentro de cuantas horas se pronostica
# Variables que NO se evaluan contra limites sino que se pronostican (en un sitio controlado no los cruzan)
PRONOSTICO = {"temperature", "humidity"}


def _reiniciar(puntos, salto):
    """Descarta lo anterior al ultimo salto brusco (cambio de regimen, p. ej. riego). Devuelve (puntos, hubo_reinicio)."""
    inicio = 0
    for i in range(1, len(puntos)):
        if abs(puntos[i][1] - puntos[i - 1][1]) > salto:
            inicio = i
    return puntos[inicio:], inicio > 0


def pronosticar(puntos, salto, unidad="°C"):
    """Valor esperado dentro de PRON_HORAS horas, con margen de error (intervalo de prediccion ~95 %).
    Usa solo las ultimas TEMP_WINDOW_H horas. Si la pendiente no es distinguible del ruido, pronostica el valor
    actual (promedio de la ventana) en vez de extrapolar ruido. Devuelve el mismo formato que `ajustar`."""
    puntos, reinicio = _reiniciar([p for p in puntos if p[0] >= -TEMP_WINDOW_H], salto)
    n = len(puntos)
    span = puntos[-1][0] - puntos[0][0] if n else 0.0
    if n < MIN_POINTS or span < MIN_SPAN_H:
        causa = " tras un cambio brusco" if reinicio else ""
        return {"estado": "datos_insuficientes", "n": n,
                "detalle": f"{n} lecturas ({span:.1f} h){causa}; se necesitan {MIN_POINTS} y {MIN_SPAN_H:g} h para pronosticar"}
    xm = sum(x for x, _ in puntos) / n
    ym = sum(y for _, y in puntos) / n
    sxx = sum((x - xm) ** 2 for x, _ in puntos)
    if sxx == 0:
        return {"estado": "sin_datos", "n": n, "detalle": "las lecturas no tienen duración suficiente para pronosticar"}
    b = sum((x - xm) * (y - ym) for x, y in puntos) / sxx
    a = ym - b * xm
    s2 = sum((y - (a + b * x)) ** 2 for x, y in puntos) / (n - 2)
    se_b = (s2 / sxx) ** 0.5
    con_tendencia = se_b > 0 and abs(b) > 2 * se_b
    if not con_tendencia:
        b, a = 0.0, ym
        s2 = sum((y - ym) ** 2 for _, y in puntos) / (n - 1)
    ss_tot = sum((y - ym) ** 2 for _, y in puntos)
    r2 = 1 - sum((y - (a + b * x)) ** 2 for x, y in puntos) / ss_tot if ss_tot else None
    x_fin = puntos[-1][0]
    pron = []
    for h in PRON_HORAS:
        x0 = x_fin + h
        var = s2 * (1 + 1 / n + ((x0 - xm) ** 2 / sxx if con_tendencia else 0))
        valor = a + b * x0
        if unidad == "%":
            valor = min(100.0, max(0.0, valor))  # un porcentaje no sale de 0-100
        pron.append({"horas": h, "valor": round(valor, 2), "margen": round(1.96 * var ** 0.5, 2)})
    base = f"tendencia {b:+.2f} {unidad}/h" if con_tendencia else "sin tendencia (se mantiene cerca del valor actual)"
    detalle = "; ".join(f"en {h:g} h: {p['valor']:.1f} ± {p['margen']:.1f} {unidad}" for h, p in zip(PRON_HORAS, pron))
    return {"estado": "pronostico", "n": n, "r2": r2, "pendiente": b, "valor_ajustado": a + b * x_fin,
            "pronostico": pron, "detalle": f"{detalle} ({base}, últimas {TEMP_WINDOW_H:g} h)"}


def ajustar(puntos, salto):
    """puntos: [(t_horas, valor)] ordenados. Devuelve {'estado': 'ok'|motivo, 'detalle', 'n', ...}."""
    puntos, reinicio = _reiniciar(puntos, salto)
    n = len(puntos)
    span = puntos[-1][0] - puntos[0][0] if n else 0.0
    if n < MIN_POINTS or span < MIN_SPAN_H:
        causa = " tras un cambio brusco (p. ej. un riego)" if reinicio else ""
        return {"estado": "datos_insuficientes", "n": n,
                "detalle": f"{n} lecturas ({span:.1f} h){causa}; se necesitan {MIN_POINTS} y {MIN_SPAN_H:g} h para ajustar"}
    xm = sum(x for x, _ in puntos) / n
    ym = sum(y for _, y in puntos) / n
    sxx = sum((x - xm) ** 2 for x, _ in puntos)
    ss_tot = sum((y - ym) ** 2 for _, y in puntos)
    if sxx == 0 or ss_tot == 0:
        return {"estado": "sin_tendencia", "n": n, "detalle": "las lecturas no varían: no hay tendencia que proyectar"}
    pendiente = sum((x - xm) * (y - ym) for x, y in puntos) / sxx
    intercepto = ym - pendiente * xm
    ss_res = sum((y - (intercepto + pendiente * x)) ** 2 for x, y in puntos)
    r2 = 1 - ss_res / ss_tot
    if r2 < MIN_R2:
        return {"estado": "ajuste_pobre", "n": n, "r2": r2,
                "detalle": f"la tendencia no explica los datos (R²={r2:.2f} < {MIN_R2:g}); no es confiable"}
    return {"estado": "ok", "n": n, "r2": r2, "pendiente": pendiente,
            "valor_ajustado": intercepto + pendiente * puntos[-1][0], "detalle": ""}


def horas_hasta_limite(ajuste, lo, hi):
    """Horas hasta cruzar un limite segun la tendencia. Devuelve (horas, 'min'|'max', limite) o None."""
    p, v = ajuste["pendiente"], ajuste["valor_ajustado"]
    if p < 0 and v > lo:
        return (lo - v) / p, "min", lo
    if p > 0 and v < hi:
        return (hi - v) / p, "max", hi
    return None  # se aleja de los limites, o ya los supero


def _txt_horas(h):
    return f"{round(h * 60)} min" if h < 1 else f"{h:.1f} h"


def evaluar(puntos, salto, col):
    """Clasifica una variable. Devuelve el dict de estado (incluye 'cruce' = (horas, tipo, limite) si hay prediccion)."""
    a = ajustar(puntos, salto)
    if a["estado"] != "ok":
        return a
    lo, hi = WARN[col]
    v = a["valor_ajustado"]
    if not lo <= v <= hi:
        return {**a, "estado": "fuera_de_rango", "detalle": "ya está fuera del rango agronómico (lo cubre la alerta)"}
    cruce = horas_hasta_limite(a, lo, hi)
    if cruce is None:
        return {**a, "estado": "estable", "detalle": f"tendencia {a['pendiente']:+.2f}/h, se aleja de los límites"}
    horas, tipo, limite = cruce
    base = {**a, "limite_tipo": tipo, "limite": limite, "horas_hasta": horas, "cruce": cruce}
    if horas > HORIZON_H:
        return {**base, "estado": "sin_riesgo",
                "detalle": f"llegaría al {'mínimo' if tipo == 'min' else 'máximo'} de {limite:g} en ~{_txt_horas(horas)}, "
                           f"fuera del horizonte de {HORIZON_H:g} h"}
    return {**base, "estado": "prediccion", "detalle": "cruce dentro del horizonte"}


def _guardar_estado(conn, eid, col, est, t_fin):
    conn.execute(
        "INSERT INTO modelo_estado(entity_id, variable, evaluado, estado, detalle, n, r2, pendiente_h, valor_ajustado, "
        "ultima_lectura, limite_tipo, limite, horas_hasta, pronostico) "
        "VALUES (%s, %s, now(), %s, %s, %s, %s, %s, %s, to_timestamp(%s), %s, %s, %s, %s::jsonb) "
        "ON CONFLICT (entity_id, variable) DO UPDATE SET evaluado = now(), estado = EXCLUDED.estado, "
        "detalle = EXCLUDED.detalle, n = EXCLUDED.n, r2 = EXCLUDED.r2, pendiente_h = EXCLUDED.pendiente_h, "
        "valor_ajustado = EXCLUDED.valor_ajustado, ultima_lectura = EXCLUDED.ultima_lectura, "
        "limite_tipo = EXCLUDED.limite_tipo, limite = EXCLUDED.limite, horas_hasta = EXCLUDED.horas_hasta, "
        "pronostico = EXCLUDED.pronostico",
        (eid, col, est["estado"], est["detalle"], est.get("n"), est.get("r2"), est.get("pendiente"),
         est.get("valor_ajustado"), t_fin, est.get("limite_tipo"), est.get("limite"), est.get("horas_hasta"),
         json.dumps(est["pronostico"]) if est.get("pronostico") else None))


def predecir(conn):
    """Evalua todas las plantas y variables, actualiza modelo_estado y devuelve las predicciones NUEVAS
    (ya guardadas, encoladas para Telegram y publicadas como evento)."""
    nuevas = []
    entidades = [r[0] for r in conn.execute("SELECT DISTINCT entity_id FROM lectura_limpia").fetchall()]
    for eid in entidades:
        ult = conn.execute(
            "SELECT extract(epoch FROM max(ts)), extract(epoch FROM now() - max(ts)) / 60 "
            "FROM lectura_limpia WHERE entity_id = %s", (eid,)).fetchone()
        t_ult, edad = (float(ult[0]), float(ult[1])) if ult[0] is not None else (None, None)
        for col, (etiqueta, unidad, salto) in VARIABLES.items():
            if edad is None or edad > MAX_STALE_MIN:
                _guardar_estado(conn, eid, col, {"estado": "datos_viejos", "detalle":
                                f"el sensor no envía desde hace {edad:.0f} min (máx. {MAX_STALE_MIN:g})" if edad is not None
                                else "sin lecturas"}, t_ult)
                continue
            filas = conn.execute(
                f"SELECT extract(epoch FROM ts), {col} FROM lectura_limpia "
                f"WHERE entity_id = %s AND {col} IS NOT NULL "
                f"AND ts > (SELECT max(ts) FROM lectura_limpia WHERE entity_id = %s) - make_interval(secs => %s) "
                f"ORDER BY ts",
                (eid, eid, WINDOW_H * 3600),
            ).fetchall()
            if not filas:
                _guardar_estado(conn, eid, col, {"estado": "sin_datos", "detalle": "sin lecturas válidas en la ventana"}, t_ult)
                continue
            t_fin = float(filas[-1][0])
            puntos = [((float(t) - t_fin) / 3600.0, float(v)) for t, v in filas]
            est = pronosticar(puntos, salto, unidad) if col in PRONOSTICO else evaluar(puntos, salto, col)
            _guardar_estado(conn, eid, col, est, t_fin)
            if est["estado"] != "prediccion":
                continue
            horas, tipo, limite = est["cruce"]
            repetida = conn.execute(
                "SELECT 1 FROM prediccion WHERE entity_id = %s AND variable = %s AND limite_tipo = %s "
                "AND generado > now() - make_interval(secs => %s)",
                (eid, col, tipo, COOLDOWN_H * 3600),
            ).fetchone()
            if repetida:
                continue
            sev = "critical" if horas <= 1 else "warning"
            mensaje = (f"{etiqueta} llegaría al {'mínimo' if tipo == 'min' else 'máximo'} de {limite:g}{unidad} "
                       f"en ~{_txt_horas(horas)} (tendencia {est['pendiente']:+.2f} {unidad}/h, "
                       f"{est['n']} lecturas reales, R²={est['r2']:.2f})")
            fila = conn.execute(
                "INSERT INTO prediccion(entity_id, variable, limite_tipo, limite, valor_actual, pendiente_h, "
                "horas_hasta, cruce_estimado, r2, n, severidad, mensaje) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, to_timestamp(%s + %s * 3600), %s, %s, %s, %s) "
                "RETURNING id, generado, cruce_estimado",
                (eid, col, tipo, limite, est["valor_ajustado"], est["pendiente"], horas,
                 t_fin, horas, est["r2"], est["n"], sev, mensaje),
            ).fetchone()
            pred = {
                "type": "prediccion", "id": fila[0], "entity_id": eid, "variable": col, "etiqueta": etiqueta,
                "limite_tipo": tipo, "limite": limite, "horas_hasta": round(horas, 2),
                "generado": fila[1].isoformat(), "cruce_estimado": fila[2].isoformat(),
                "severidad": sev, "mensaje": mensaje,
            }
            # Telegram: se encola en esta misma transaccion (el despachador la envia despues)
            notify.encolar(conn, "prediccion", fila[0], f"{eid}|pred_{col}_{tipo}", sev,
                           f"{TITULOS[(col, tipo)]} — {eid}",
                           f"{mensaje}\nCruce estimado: {notify.hora_local(fila[2])}")
            # Navegador: se entrega al hacer commit (la API hace LISTEN y lo empuja por websocket)
            conn.execute("SELECT pg_notify('eventos', %s)", (json.dumps(pred),))
            nuevas.append(pred)
    return nuevas

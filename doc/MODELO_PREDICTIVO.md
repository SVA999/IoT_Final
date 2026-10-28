# Modelo predictivo y notificaciones en vivo

## Regla de oro: solo datos reales
El modelo se alimenta **únicamente** de las lecturas que envía el end device (tabla `lectura_limpia`). No hay datos sintéticos,
valores de relleno ni semillas. Si no hay evidencia suficiente, **no predice**.

## Qué hace
> **Temperatura y humedad del aire:** no se evalúan contra límites (en un sitio controlado no los cruzan). Se **pronostica** su valor a +1, +3 y +6 h
> con margen de error (intervalo de predicción ~95 %), usando solo las últimas 2 h (`PRED_TEMP_WINDOW_H`). Si la pendiente no se
> distingue del ruido, el pronóstico es el valor actual. No genera avisos de Telegram; las alertas de rango siguen activas.

Para cada planta, y para `soil_moisture`, ajusta una recta (mínimos cuadrados) a las lecturas de las
últimas 6 h y estima **cuándo cruzaría el límite agronómico** (`app/etl/config.py → WARN`). Si el cruce ocurre en ≤ 6 h, guarda una
fila en `prediccion` y notifica. Ejemplo: *"Humedad del suelo llegaría al mínimo de 20% en ~2.4 h (tendencia −4.00 %/h, 40 lecturas reales, R²=0.99)"*.

La luminosidad **no** se modela: es cíclica (día/noche) y una recta no la representa.

## Cuándo NO predice (por diseño)
| Condición | Parámetro (variable de entorno) | Por defecto |
|---|---|---|
| Pocas lecturas | `PRED_MIN_POINTS` / `PRED_MIN_SPAN_H` | 12 lecturas y ≥ 1 h |
| Ajuste malo (ruido) | `PRED_MIN_R2` | R² ≥ 0.6 |
| Datos viejos (sensor apagado) | `PRED_MAX_STALE_MIN` | última lectura ≤ 30 min |
| Cambio brusco (p. ej. un riego) | salto por variable en `predict.py` | la ventana se reinicia tras el salto |
| La variable se aleja del límite o ya lo superó | — | (la alerta normal ya cubre lo segundo) |

No repite el mismo aviso dentro de `PRED_COOLDOWN_H` (3 h). Las alertas de umbral tampoco: una por condición (`ALERT_COOLDOWN_MIN`, 30 min).

## Estados del modelo (pantalla *Predicciones*)
Cada variable muestra su estado y el motivo, aunque no haya predicción: `prediccion`, `sin_riesgo` (cruzaría el límite pero más allá de 6 h),
`estable`, `fuera_de_rango`, `datos_insuficientes`, `sin_tendencia`, `ajuste_pobre`, `datos_viejos`, `sin_datos`. Se guardan en `modelo_estado`.
El gráfico dibuja las lecturas reales, la tendencia proyectada (punteada), el límite y el punto de cruce estimado.

## Flujo de la notificación
```
evento de Orion -> processor -> ETL -> predict.py -> INSERT prediccion + pg_notify('eventos') + bandeja de salida
   -> API (LISTEN, por eventos) -> WebSocket /api/ws -> navegador: aviso emergente + pantalla "Predicciones"
   -> despachador -> Telegram (doc/NOTIFICACIONES.md)
```
- El token se envía como **primer mensaje** del websocket (no va en la URL). Token inválido → cierre con código 4401 y vuelve al login.
- El navegador manda `ping` cada 25 s. Si la conexión cae, reintenta con espera creciente **hasta 8 veces**; después muestra la campana en rojo
  y se reintenta con un clic (no hay bucle infinito).
- Eventos que recibe el navegador: `lecturas`, `alerta`, `prediccion` y `modelo`; con cada uno se recargan los datos (no hay `setInterval`).
  Solo si el websocket cae del todo se sondea despacio (cada 60 s) para no quedar ciego.
- Las predicciones previas se cargan por REST (`GET /api/predicciones`), así que no se pierden al recargar la página.

## ETL sin ciclo infinito
`etl.py` no es un proceso eterno: procesa lo pendiente (en lotes, con tope `ETL_MAX_BATCHES`), termina y devuelve 0/1.
Lo dispara **un evento** (suscripción de Orion → servicio `processor`) y, como red de seguridad, un cron cada 30 min con `flock` y `timeout`.
Un candado de Postgres impide que dos corridas se solapen. Es idempotente y transaccional.

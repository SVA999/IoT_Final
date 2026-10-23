# Notificaciones por Telegram

Cada **alerta** nueva y cada **predicción** nueva del modelo (p. ej. *"Se va a acabar el agua del suelo"*) llega al chat de Telegram,
además de aparecer como aviso emergente en el front.

## Por qué Telegram (y no correo o WhatsApp)
| Canal | Qué exige | Veredicto |
|---|---|---|
| **Telegram** | Un bot de @BotFather (2 min), gratis, una llamada HTTPS | ✅ **el más fácil y adecuado** |
| Correo (SMTP) | Cuenta con contraseña de aplicación/2FA, riesgo de ir a spam; AWS Academy limita el correo saliente | posible, más fricción |
| WhatsApp | WhatsApp Business API: verificar empresa, aprobar plantillas de mensajes, costo por conversación | ❌ el más difícil |

## Configuración (una sola vez)
1. En Telegram abre **@BotFather** → `/newbot` → pon nombre y usuario. Te entrega el **token** (`123456:ABC...`). Es secreto.
2. Abre el chat con tu bot nuevo y envíale `/start` (o agrégalo a un grupo y escribe algo).
3. Obtén tu **chat id**:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
   Busca `"chat":{"id": 123456789` (en grupos el id es negativo). Varios destinatarios: sepáralos con coma.
4. Ponlos donde corresponda:
   - **Terraform:** `telegram_bot_token` y `telegram_chat_ids` en `terraform.tfvars`.
   - **Instancia ya creada / local:** en `.env` → `TELEGRAM_BOT_TOKEN=...` y `TELEGRAM_CHAT_IDS=...`, luego
     `docker compose up -d --build processor etl`.
5. Prueba: `curl "https://api.telegram.org/bot<TOKEN>/sendMessage" -d chat_id=<ID> -d text=prueba`.

Sin token, el sistema funciona igual: los avisos quedan registrados como `sin_canal` (se ven en la pantalla *Predicciones*).

## Qué se envía y qué no
- **Predicciones**: todas las del modelo (1 por variable cada 3 h como máximo).
- **Alertas**: advertencias (valor fuera de rango) y errores (lectura inválida del sensor), una por condición cada 30 min.
- **No se envían** las alertas de **luminosidad** (de noche es normal que haya poca luz): `NOTIFY_IGNORE_VARS`.
- **No se avisa de datos viejos**: si el sistema se pone al día tras una caída, solo notifica lo ocurrido en la última hora (`NOTIFY_MAX_AGE_MIN`).
- **No se repite** el mismo aviso en 2 h (`NOTIFY_COOLDOWN_MIN`).

## Cómo garantiza que no se pierdan ni se repitan (bandeja de salida)
Cada aviso se guarda primero en la tabla `notificacion` (en la misma transacción que crea la alerta/predicción) y un despachador lo envía:
- Si Telegram falla, **reintenta** en la siguiente corrida, hasta 5 veces; luego queda `fallida` (visible en la pantalla *Predicciones*).
- Si hay varios chats y alguno falla, los demás reciben el aviso y el fallo queda anotado en `detalle`.
- El **token nunca se escribe en los logs** (solo el tipo de error).

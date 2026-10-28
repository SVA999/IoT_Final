CREATE TABLE IF NOT EXISTS lectura_limpia (
  entity_id     TEXT        NOT NULL,
  ts            TIMESTAMPTZ NOT NULL,
  temperature   DOUBLE PRECISION,
  humidity      DOUBLE PRECISION,
  luminosity    DOUBLE PRECISION,
  soil_moisture DOUBLE PRECISION,
  lat DOUBLE PRECISION,
  lon DOUBLE PRECISION,
  PRIMARY KEY (entity_id, ts)
);

CREATE TABLE IF NOT EXISTS resumen_horario (
  entity_id TEXT        NOT NULL,
  hora      TIMESTAMPTZ NOT NULL,
  temp_avg DOUBLE PRECISION,
  temp_min DOUBLE PRECISION,
  temp_max DOUBLE PRECISION,
  hum_avg  DOUBLE PRECISION,
  lux_avg  DOUBLE PRECISION,
  soil_avg DOUBLE PRECISION,
  n INT,
  PRIMARY KEY (entity_id, hora)
);

CREATE TABLE IF NOT EXISTS alerta (
  id        BIGSERIAL PRIMARY KEY,
  entity_id TEXT        NOT NULL,
  ts        TIMESTAMPTZ NOT NULL,
  severidad TEXT        NOT NULL CHECK (severidad IN ('warning', 'error')),
  tipo      TEXT        NOT NULL,
  mensaje   TEXT        NOT NULL,
  UNIQUE (entity_id, ts, tipo)
);

-- Predicciones del modelo de tendencia (app/etl/predict.py). Solo se generan a partir de lecturas reales.
CREATE TABLE IF NOT EXISTS prediccion (
  id             BIGSERIAL PRIMARY KEY,
  entity_id      TEXT        NOT NULL,
  variable       TEXT        NOT NULL,
  generado       TIMESTAMPTZ NOT NULL DEFAULT now(),
  limite_tipo    TEXT        NOT NULL CHECK (limite_tipo IN ('min', 'max')),
  limite         DOUBLE PRECISION NOT NULL,
  valor_actual   DOUBLE PRECISION NOT NULL,
  pendiente_h    DOUBLE PRECISION NOT NULL,
  horas_hasta    DOUBLE PRECISION NOT NULL,
  cruce_estimado TIMESTAMPTZ NOT NULL,
  r2             DOUBLE PRECISION NOT NULL,
  n              INT         NOT NULL,
  severidad      TEXT        NOT NULL CHECK (severidad IN ('warning', 'critical')),
  mensaje        TEXT        NOT NULL
);
CREATE INDEX IF NOT EXISTS prediccion_generado_idx ON prediccion (generado DESC);

-- Estado actual del modelo por planta y variable (se actualiza en cada corrida; la pantalla "Predicciones" lo muestra).
-- estado: prediccion | sin_riesgo | estable | fuera_de_rango | datos_insuficientes | sin_tendencia | ajuste_pobre | datos_viejos | sin_datos
CREATE TABLE IF NOT EXISTS modelo_estado (
  entity_id       TEXT        NOT NULL,
  variable        TEXT        NOT NULL,
  evaluado        TIMESTAMPTZ NOT NULL DEFAULT now(),
  estado          TEXT        NOT NULL,
  detalle         TEXT        NOT NULL,
  n               INT,
  r2              DOUBLE PRECISION,
  pendiente_h     DOUBLE PRECISION,
  valor_ajustado  DOUBLE PRECISION,
  ultima_lectura  TIMESTAMPTZ,
  limite_tipo     TEXT,
  limite          DOUBLE PRECISION,
  horas_hasta     DOUBLE PRECISION,
  PRIMARY KEY (entity_id, variable)
);
-- Pronostico de valores futuros (temperatura): lista [{horas, valor, margen}]. Se agrega aparte para bases ya creadas.
ALTER TABLE modelo_estado ADD COLUMN IF NOT EXISTS pronostico JSONB;

-- Bandeja de salida de notificaciones externas (Telegram). Cada alerta/prediccion nueva se encola aqui y un
-- despachador la envia: asi un fallo de red no pierde el aviso, y hay limite de reintentos y de repeticion.
CREATE TABLE IF NOT EXISTS notificacion (
  id         BIGSERIAL PRIMARY KEY,
  origen     TEXT        NOT NULL CHECK (origen IN ('alerta', 'prediccion')),
  origen_id  BIGINT      NOT NULL,
  clave      TEXT        NOT NULL,                 -- planta|tipo: para no repetir el mismo aviso
  severidad  TEXT        NOT NULL,
  titulo     TEXT        NOT NULL,
  mensaje    TEXT        NOT NULL,
  creada     TIMESTAMPTZ NOT NULL DEFAULT now(),
  enviada    TIMESTAMPTZ,
  estado     TEXT        NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'enviada', 'suprimida', 'fallida', 'sin_canal')),
  intentos   INT         NOT NULL DEFAULT 0,
  detalle    TEXT,
  UNIQUE (origen, origen_id)
);
CREATE INDEX IF NOT EXISTS notificacion_estado_idx ON notificacion (estado, id);

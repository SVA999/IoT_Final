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

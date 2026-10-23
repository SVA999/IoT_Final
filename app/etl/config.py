"""Umbrales compartidos por el ETL y el modelo predictivo. Ajustar al cultivo."""

# Rangos fisicos validos: fuera de ellos la lectura es un error del sensor (p. ej. el firmware manda -999)
VALID = {"temperature": (-10, 60), "humidity": (0, 100), "luminosity": (0, 120000), "soil_moisture": (0, 100)}

# Rangos agronomicos: fuera de ellos se genera una advertencia
WARN = {"temperature": (10, 35), "humidity": (30, 90), "luminosity": (1000, 80000), "soil_moisture": (20, 80)}

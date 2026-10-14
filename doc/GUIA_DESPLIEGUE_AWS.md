# Guía de despliegue en AWS (AWS Academy Learner Lab)

> Asume **AWS Academy Learner Lab**: región `us-east-1`, sin crear roles IAM (se usa el `LabInstanceProfile` existente), llave `vockey`, **sin IP elástica** (la IP pública cambia al detener/iniciar la instancia) y credenciales temporales.

Dos caminos para el mismo resultado: **A) manual** (consola de AWS, ideal para entender cada pieza) y **B) Terraform** (un comando, repetible). Ambos terminan con la misma EC2 corriendo `docker-compose.yml`.

## 0. Requisitos previos (ambos caminos)

1. **Cuenta de AWS** con permisos para EC2 y VPC.
2. **Repo en GitHub y público** (el servidor lo clona sin credenciales). Desde tu PC:
   ```bash
   git add -A && git commit -m "Arquitectura IoT final" && git push
   ```
3. **Tu IP pública**: abre https://checkip.amazonaws.com y anótala. Se usa como `TU_IP/32`.
4. **Entrar al Learner Lab:** Academy → tu curso → *Modules* → *Learner Lab* → **Start Lab** (espera el círculo verde) → **AWS Details** → *Download PEM* (`labsuite.pem`, es la llave `vockey`) y *AWS CLI: Show* (credenciales temporales). En Linux/Mac: `chmod 400 labsuite.pem`. El botón **AWS** abre la consola.
5. **Región:** usa **us-east-1**.

### Qué se va a crear y cuánto cuesta (orientativo)
| Recurso | Detalle | Costo aprox. |
|---|---|---|
| EC2 t3.large | 2 vCPU, 8 GB RAM | ~0.083 USD/hora (~60 USD/mes encendida) |
| Disco gp3 | 24 GB | ~2 USD/mes |
| Crédito | Se descuenta del presupuesto del Lab; al agotarse, el entorno se reinicia | — |

Apaga o destruye todo cuando no lo uses. Revisa precios vigentes en la calculadora de AWS.

---

## A) Montaje manual (consola de AWS)

### A1. Crear el Security Group
EC2 → *Security Groups* → **Create security group**.
- Nombre: `plantas-sg`; VPC: la default.
- **Inbound rules** (Add rule, tipo *Custom TCP*):

| Puerto | Origen | Para qué |
|---|---|---|
| 22 | `TU_IP/32` | SSH |
| 80 | `0.0.0.0/0` | Front |
| 443 | `0.0.0.0/0` | Front HTTPS (futuro) |
| 1036 | `0.0.0.0/0` | Orion (lo usan los gateways; el device no tiene IP propia) |
| 7896 | `0.0.0.0/0` | Agente IoT (donde publica el gateway del sensor) |
| 4200 | `TU_IP/32` | Consola de CrateDB |
| 3000 | `TU_IP/32` | Grafana |

- Outbound: dejar el valor por defecto (todo permitido).
- No abras 4041, 1026, 27017, 5432 ni 8000: son internos.

### A2. Lanzar la instancia
EC2 → **Launch instance**.
1. **Name:** `plantas-iot`.
2. **AMI:** *Ubuntu Server* (26.04 LTS si aparece; si no, 24.04 LTS). Arquitectura **64-bit (x86)**.
3. **Instance type:** `t3.large`.
4. **Key pair:** `vockey` (la del Lab).
5. **Network settings → Select existing security group:** `plantas-sg`.
6. **Storage:** 24 GiB, tipo **gp3**.
7. **Advanced details → IAM instance profile:** `LabInstanceProfile` (Academy no permite crear roles).
8. *Launch instance*.

### A3. IP pública (sin IP elástica)
En la instancia copia **Public IPv4 address**. **Cambia cada vez que detienes e inicias la instancia** (p. ej. al terminar la sesión del Lab): usa la nueva para el front y SSH, y avisa al equipo del gateway.

### A4. Entrar por SSH
```bash
ssh -i labsuite.pem ubuntu@IP_PUBLICA
```

### A5. Preparar el servidor
```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git curl
sudo usermod -aG docker $USER && newgrp docker

# Obligatorio para CrateDB (si falta, el contenedor se reinicia en bucle)
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### A6. Traer y configurar el proyecto
```bash
git clone https://github.com/USUARIO/IoT_Final.git
cd IoT_Final
cp .env.example .env
nano .env          # cambia DWH_PASSWORD, FRONT_PASSWORD, AUTH_SECRET (openssl rand -hex 32) y pon GEMINI_API_KEY
                   # (guarda con Ctrl+O, sal con Ctrl+X)
```

### A7. Levantar los servicios
```bash
docker compose up -d --build     # la primera vez tarda varios minutos
docker compose ps                # todos "running" (etl/api pueden reiniciar hasta que haya datos)
```

### A8. Provisionar el agente y la suscripción
Espera ~1 minuto y ejecuta:
```bash
bash doc/provisionar.sh localhost
```
Deben salir tres respuestas `HTTP/1.1 201 Created`. Esto registra el grupo de servicio, el dispositivo `planta01` y la suscripción Orion → QuantumLeap. Solo se hace una vez.

### A9. Probar con un sensor simulado
```bash
curl -X POST "http://localhost:7896/iot/json?k=plantas2026&i=planta01" \
  -H 'Content-Type: application/json' \
  -d '{"t":24.5,"h":60,"l":15000,"s":45}'
```
Para disparar una alerta: repite con `"t":50` o `"s":5`.

---

## B) Montaje con Terraform

### B1. Instalar herramientas (en tu PC)
- **Terraform:** https://developer.hashicorp.com/terraform/install (Windows: `winget install Hashicorp.Terraform`).
- **AWS CLI:** https://aws.amazon.com/cli/ (Windows: `winget install Amazon.AWSCLI`).
- Comprueba: `terraform -version` y `aws --version`.

### B2. Credenciales de AWS (temporales del Learner Lab)
En Academy no se crean access keys propias. Cada sesión entrega credenciales temporales:
1. Learner Lab -> **Start Lab** -> **AWS Details** -> **AWS CLI: Show**.
2. Pega el bloque en `~/.aws/credentials` (Windows: `C:/Users/TU_USUARIO/.aws/credentials`):
   ```ini
   [default]
   aws_access_key_id=ASIA...
   aws_secret_access_key=...
   aws_session_token=...
   ```
3. `aws configure set region us-east-1`
4. Comprueba: `aws sts get-caller-identity` (rol tipo `voclabs`).
5. **Expiran** al terminar la sesión (~4 h) y cambian cada vez: si Terraform da `ExpiredToken`/`AuthFailure`, repite. No las subas a git.
6. Si el Lab se reinicia y la instancia desaparece, borra `terraform.tfstate*` y `.terraform/` antes de volver a aplicar.

### B3. Preparar variables
Haz los pasos 0.2 a 0.5 (repo público, tu IP, Key Pair).
```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```
Edita `terraform.tfvars`:
```hcl
region       = "us-east-1"
key_name     = "vockey"
admin_cidr   = "TU_IP/32"
repo_url     = "https://github.com/USUARIO/IoT_Final.git"
dwh_password = "una-clave-segura"
front_user     = "admin"
front_password = "clave-del-front"
gemini_api_key = "AIza..."          # https://aistudio.google.com/apikey (opcional)
# ubuntu_version = "24.04"          # descomenta si no hay AMI 26.04 en tu región
```

### B4. Desplegar
```bash
terraform init        # descarga el proveedor AWS
terraform validate
terraform plan        # revisa que cree: SG, EC2, IP elástica
terraform apply       # escribe "yes"
```
Al terminar muestra las `outputs`: IP pública, URL del front, URL de Orion, URL para el device y el comando SSH (con `labsuite.pem`). Terraform usa `LabInstanceProfile` por defecto; no crea roles.

### B5. Esperar el arranque automático
La instancia ya existe, pero aún está instalando. Entra y sigue el log:
```bash
ssh -i labsuite.pem ubuntu@IP
sudo tail -f /var/log/plantas-bootstrap.log
```
Termina cuando aparece `BOOTSTRAP OK` (5–10 min). Ahí ya está todo levantado **y provisionado**: no hay que correr nada más. Haz la prueba del paso A9.

### B6. Cambios posteriores
- **Cambió el código de la app:** haz push, entra por SSH y ejecuta `cd /opt/IoT_Final && git pull && docker compose up -d --build`. (Terraform no re-clona; el bootstrap solo corre al crear.)
- **Cambió la infraestructura** (IP permitida, tipo de instancia): edita `tfvars` y `terraform apply`. Ojo: cambiar `repo_url` o `dwh_password` **recrea la instancia** y pierde los datos.

### B7. Borrar todo
```bash
terraform destroy
```

---

## Verificación (ambos caminos)

| Qué | Cómo | Esperado |
|---|---|---|
| Orion vivo | `http://IP:1036/version` en el navegador | JSON con versión |
| Dato en Orion | `curl localhost:1036/v2/entities -H 'fiware-service: openiot' -H 'fiware-servicepath: /'` | entidad `planta01` |
| QuantumLeap/Crate | `http://IP:4200` → consola SQL: `SELECT * FROM mtopeniot.etplantsensor` | filas |
| ETL | `docker logs etl` | `ETL ok: N lecturas` (cada 5 min; `docker restart etl` fuerza uno) |
| DWH | `docker exec dwh-postgres psql -U dwh -d plantas -c "select * from lectura_limpia"` | filas |
| API | `curl http://IP/api/plantas` | JSON |
| Front | `http://IP` | pantalla de login; luego tarjeta de la planta, alertas, chat con Gemini |

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `crate-db` se reinicia | Falta `vm.max_map_count` o poca RAM. Aplica el `sysctl` o baja `CRATE_HEAP_SIZE` a `1g`. |
| `etl` dice "table doesn't exist" | Normal hasta que llega el primer dato. Envía el curl del A9. |
| `provisionar.sh` da 4xx / `Connection refused` | El agente aún arranca. Espera y repite; revisa `docker logs iot-agent`. |
| Front carga pero sin datos | Aún no corrió el ETL (`docker restart etl`) o falla la API (`docker logs api`). |
| No conecto por SSH | Tu IP cambió: actualiza la regla 22 del SG (o `admin_cidr` y `terraform apply`). |
| `terraform apply`: AMI no encontrada | Pon `ubuntu_version = "24.04"`. |
| `terraform apply`: key pair no existe | En Academy es `vockey` y la región `us-east-1`. |
| `ExpiredToken` / `AuthFailure` | Expiraron las credenciales del Lab: repite B2. |
| Perfil IAM no encontrado / `PassRole` | Usa exactamente `LabInstanceProfile`; no crees roles. |
| Cambió la IP tras reiniciar el Lab | Esperable sin IP elástica: `terraform output ip_publica` y avisa al equipo del gateway. Los contenedores arrancan solos (`restart: unless-stopped`). |
| Bootstrap falló al clonar | El repo es privado o la URL está mal. Mira `/var/log/plantas-bootstrap.log`. |
| `mongo` no arranca | `mongo:4.4` necesita CPU con AVX; la t3 lo tiene, otras familias pueden no. |

## Pendiente para producción
HTTPS en 443 (certificado; sin él el login viaja en claro), autenticación en Orion, cerrar 4200 y 3000, y respaldar los volúmenes de Docker.

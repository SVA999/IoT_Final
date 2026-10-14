# IoT_Final – Monitoreo de plantas

Plataforma FIWARE en AWS (EC2) para monitorear plantas. El end device (TTGO T-Beam) lo desarrolla otro equipo; aquí solo está la arquitectura de nube.
Arquitectura completa, decisiones y pendientes: [doc/ARQUITECTURA.md](doc/ARQUITECTURA.md).

```
app/
  etl/        ETL Python (CrateDB -> limpiar -> analizar -> Postgres + alertas a Orion)
  dwh/        Esquema Postgres (init.sql)
  api_ai/     API FastAPI + chat con IA
  frontend/   React + Vite + Tailwind (build multi-etapa -> nginx)
infra/        Infraestructura AWS (Security Group, scripts)
doc/          Documentación y comandos de ejemplo
```

## Levantar

```bash
sudo sysctl -w vm.max_map_count=262144
cp .env.example .env     # editar DWH_PASSWORD
docker compose up -d --build
```

## Desplegar en AWS con Terraform

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # completar
terraform init && terraform apply
```
Crea la EC2, el Security Group y la IP elástica; la instancia instala Docker, clona el repo, levanta el compose y provisiona el agente. Ver `outputs` para las URLs.

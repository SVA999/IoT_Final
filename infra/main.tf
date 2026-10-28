terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_availability_zones" "disponibles" {
  state = "available"
}

locals {
  az = var.availability_zone != "" ? var.availability_zone : data.aws_availability_zones.disponibles.names[0]

  # "usuario/repositorio" a partir de la URL (https://github.com/usuario/repo.git)
  repo_slug = try(regex("github\\.com[/:]([^/]+/[^/]+?)(?:\\.git)?/?$", var.repo_url)[0], "")

  # Version a desplegar: el ultimo commit de la rama, o el commit fijado en repo_ref
  repo_version = var.repo_ref != "" ? var.repo_ref : trimspace(data.http.ultimo_commit[0].response_body)
}

# Ultimo commit de la rama en GitHub. Asi un push cambia el user_data y el siguiente `terraform apply` lo despliega
# (la instancia se recrea; los datos NO se pierden porque viven en el disco aparte).
data "http" "ultimo_commit" {
  count = var.repo_ref == "" ? 1 : 0
  url   = "https://api.github.com/repos/${local.repo_slug}/commits/${var.repo_branch}"

  request_headers = {
    Accept = "application/vnd.github.sha"
  }

  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "No se pudo consultar el ultimo commit en GitHub (repo privado, URL que no es de GitHub o limite de consultas). Define repo_ref con el commit a desplegar."
    }
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-*-${var.ubuntu_version}-amd64-server-*"]
  }
}

resource "aws_security_group" "plantas" {
  name        = "plantas-sg"
  description = "Monitoreo de plantas"

  dynamic "ingress" {
    for_each = {
      ssh     = { port = 22, cidrs = concat([var.admin_cidr], var.admin_cidrs_extra) }
      http    = { port = 80, cidrs = ["0.0.0.0/0"] }
      https   = { port = 443, cidrs = ["0.0.0.0/0"] }
      orion   = { port = 1036, cidrs = ["0.0.0.0/0"] }
      agente  = { port = 7896, cidrs = ["0.0.0.0/0"] }
      crate   = { port = 4200, cidrs = concat([var.admin_cidr], var.admin_cidrs_extra) }
      grafana = { port = 3000, cidrs = concat([var.admin_cidr], var.admin_cidrs_extra) }
    }
    content {
      description = ingress.key
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = "tcp"
      cidr_blocks = ingress.value.cidrs
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "plantas" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  iam_instance_profile   = var.iam_instance_profile # AWS Academy: perfil preexistente, no se pueden crear roles
  vpc_security_group_ids = [aws_security_group.plantas.id]
  availability_zone      = local.az # el disco de datos solo se puede adjuntar si esta en la misma zona

  root_block_device {
    volume_size = var.disk_gb
    volume_type = "gp3"
  }

  user_data = replace(templatefile("${path.module}/user_data.sh.tftpl", {
    repo_url           = var.repo_url
    repo_version       = local.repo_version
    data_volume_id     = replace(aws_ebs_volume.datos.id, "-", "")
    dwh_password       = var.dwh_password
    front_user         = var.front_user
    front_password     = var.front_password
    auth_secret        = var.auth_secret
    gemini_api_key     = var.gemini_api_key
    gemini_model       = var.gemini_model
    crate_password     = var.crate_password
    telegram_bot_token = var.telegram_bot_token
    telegram_chat_ids  = var.telegram_chat_ids
    timezone           = var.timezone
  }), "\r\n", "\n") # evita CRLF si el .tftpl se edita en Windows (rompe el script en Linux)
  user_data_replace_on_change = true

  associate_public_ip_address = true

  tags = { Name = "plantas-iot" }
}

# Disco de DATOS: Orion/Mongo, CrateDB (historico crudo), Postgres (DWH), Grafana e imagenes de Docker.
# Vive aparte de la instancia: terraform apply puede recrearla con el codigo nuevo y el historico se conserva.
# prevent_destroy: un `terraform destroy` accidental NO borra el historico. Para borrarlo a proposito (fin del proyecto),
# elimina el bloque lifecycle de aqui.
resource "aws_ebs_volume" "datos" {
  availability_zone = local.az
  size              = var.data_disk_gb
  type              = "gp3"
  tags              = { Name = "plantas-datos" }

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_volume_attachment" "datos" {
  device_name                    = "/dev/sdf"
  volume_id                      = aws_ebs_volume.datos.id
  instance_id                    = aws_instance.plantas.id
  stop_instance_before_detaching = true # al recrear la instancia se detiene limpia antes de soltar el disco (sin corromper las bases)
}

# IP fija: sobrevive a detener/iniciar y a recrear la instancia (terraform apply -replace)
resource "aws_eip" "plantas" {
  domain  = "vpc"
  address = var.eip_address != "" ? var.eip_address : null # recupera una IP liberada (la del chip) en vez de pedir una nueva
  tags    = { Name = "plantas-iot" }

  # La IP queda grabada en el programa del sensor: si se libera, AWS NO la devuelve y hay que reprogramar el chip.
  # prevent_destroy impide perderla por accidente (terraform destroy, o un cambio que la reemplace). Para liberarla a
  # proposito (fin del proyecto), elimina este bloque.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_eip_association" "plantas" {
  instance_id   = aws_instance.plantas.id
  allocation_id = aws_eip.plantas.id
}

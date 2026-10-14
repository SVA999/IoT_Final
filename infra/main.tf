terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
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
      ssh     = { port = 22, cidr = var.admin_cidr }
      http    = { port = 80, cidr = "0.0.0.0/0" }
      https   = { port = 443, cidr = "0.0.0.0/0" }
      orion   = { port = 1036, cidr = "0.0.0.0/0" }
      agente  = { port = 7896, cidr = "0.0.0.0/0" }
      crate   = { port = 4200, cidr = var.admin_cidr }
      grafana = { port = 3000, cidr = var.admin_cidr }
    }
    content {
      description = ingress.key
      from_port   = ingress.value.port
      to_port     = ingress.value.port
      protocol    = "tcp"
      cidr_blocks = [ingress.value.cidr]
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
  vpc_security_group_ids = [aws_security_group.plantas.id]

  root_block_device {
    volume_size = var.disk_gb
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    repo_url     = var.repo_url
    dwh_password   = var.dwh_password
    front_user     = var.front_user
    front_password = var.front_password
    gemini_api_key = var.gemini_api_key
  })
  user_data_replace_on_change = true

  tags = { Name = "plantas-iot" }
}

resource "aws_eip" "plantas" {
  instance = aws_instance.plantas.id
  domain   = "vpc"
}

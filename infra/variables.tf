variable "region" {
  type    = string
  default = "us-east-1"
}

variable "key_name" {
  description = "Nombre de un Key Pair EC2 ya existente (para SSH)"
  type        = string
}

variable "admin_cidr" {
  description = "Tu IP publica en CIDR (ej. 190.1.2.3/32): SSH, Crate UI y Grafana"
  type        = string
}

variable "device_cidr" {
  description = "Origen permitido hacia Orion (1036) y Agente (7896): IP del end device/gateway. 0.0.0.0/0 si no se conoce."
  type        = string
  default     = "0.0.0.0/0"
}

variable "repo_url" {
  description = "URL https del repo con este proyecto (publico, o con token embebido)"
  type        = string
}

variable "dwh_password" {
  description = "Password del Postgres DWH"
  type        = string
  sensitive   = true
}

variable "ubuntu_version" {
  description = "Version de Ubuntu para la AMI. Si 26.04 no tiene AMI en tu region, usar 24.04"
  type        = string
  default     = "26.04"
}

variable "instance_type" {
  type    = string
  default = "t3.large"
}

variable "disk_gb" {
  type    = number
  default = 24
}

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

variable "repo_url" {
  description = "URL https del repo con este proyecto (publico, o con token embebido)"
  type        = string
}

variable "dwh_password" {
  description = "Password del Postgres DWH"
  type        = string
  sensitive   = true
}

variable "front_user" {
  type    = string
  default = "admin"
}

variable "front_password" {
  description = "Password de acceso al front"
  type        = string
  sensitive   = true
}

variable "gemini_api_key" {
  description = "API key de Gemini (https://aistudio.google.com/apikey). Vacia = chat deshabilitado"
  type        = string
  sensitive   = true
  default     = ""
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

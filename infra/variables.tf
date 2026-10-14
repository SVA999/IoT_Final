variable "region" {
  description = "AWS Academy Learner Lab solo permite us-east-1 (y a veces us-west-2)"
  type        = string
  default     = "us-east-1"
}

variable "key_name" {
  description = "Key Pair EC2 existente. En AWS Academy ya existe 'vockey'"
  type        = string
  default     = "vockey"
}

variable "iam_instance_profile" {
  description = "Instance profile preexistente. En AWS Academy: LabInstanceProfile (rol LabRole)"
  type        = string
  default     = "LabInstanceProfile"
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

variable "crate_password" {
  description = "Password del usuario 'crate' de CrateDB (UI :4200, QuantumLeap, ETL, Grafana)"
  type        = string
  sensitive   = true
}

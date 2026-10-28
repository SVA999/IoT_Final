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

  validation {
    condition     = can(cidrhost(var.admin_cidr, 0))
    error_message = "admin_cidr debe ser un CIDR valido, p. ej. 190.1.2.3/32 (tu IP publica: https://checkip.amazonaws.com)."
  }
}

variable "admin_cidrs_extra" {
  description = "IP publicas adicionales en CIDR con el mismo acceso admin (por si tu proveedor rota la IP entre dos)"
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for c in var.admin_cidrs_extra : can(cidrhost(c, 0))])
    error_message = "Cada elemento de admin_cidrs_extra debe ser un CIDR valido, p. ej. 190.1.2.3/32."
  }
}

variable "repo_url" {
  description = "URL https del repo con este proyecto (publico, o con token embebido)"
  type        = string
}

variable "repo_branch" {
  description = "Rama a desplegar"
  type        = string
  default     = "main"
}

variable "repo_ref" {
  description = "Commit exacto a desplegar. VACIO (recomendado) = el ultimo commit de repo_branch en GitHub, consultado en cada apply: cada push se despliega con un terraform apply. Definelo si el repo es privado."
  type        = string
  default     = ""
}

variable "dwh_password" {
  description = "Password del Postgres DWH"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.dwh_password) >= 8 && can(regex("^[^'\"$\\\\`\\s]+$", var.dwh_password)) && !startswith(var.dwh_password, "CAMBIAR")
    error_message = "dwh_password: minimo 8 caracteres, sin comillas, $, barra invertida ni espacios (rompen el .env) y distinta del texto CAMBIAR..."
  }
}

variable "front_user" {
  type    = string
  default = "admin"
}

variable "front_password" {
  description = "Password de acceso al front"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.front_password) >= 8 && can(regex("^[^'\"$\\\\`\\s]+$", var.front_password)) && !startswith(var.front_password, "CAMBIAR")
    error_message = "front_password: minimo 8 caracteres, sin comillas, $, barra invertida ni espacios (rompen el .env) y distinta del texto CAMBIAR..."
  }
}

variable "auth_secret" {
  description = "Secreto con el que la API firma las sesiones. Vacio = se genera uno aleatorio en cada instancia (las sesiones abiertas se cierran al recrearla)"
  type        = string
  sensitive   = true
  default     = ""

  validation {
    condition     = var.auth_secret == "" || (length(var.auth_secret) >= 32 && can(regex("^[A-Za-z0-9_.-]+$", var.auth_secret)))
    error_message = "auth_secret: vacio, o minimo 32 caracteres alfanumericos (puedes usar: openssl rand -hex 32)."
  }
}

variable "gemini_api_key" {
  description = "API key de Gemini (https://aistudio.google.com/apikey). Vacia = chat deshabilitado"
  type        = string
  sensitive   = true
  default     = ""

  validation {
    condition     = var.gemini_api_key == "" || can(regex("^[A-Za-z0-9_.-]+$", var.gemini_api_key))
    error_message = "gemini_api_key tiene caracteres no validos: se permiten letras, numeros, punto, guion y guion bajo (copiala completa y sin comillas ni espacios)."
  }
}

variable "gemini_model" {
  description = "Modelo de Gemini. Si responde 404, usa uno vigente de https://ai.google.dev/gemini-api/docs/models"
  type        = string
  default     = "gemini-3.6-flash"
}

variable "telegram_bot_token" {
  description = "Token del bot de Telegram (@BotFather) para avisos de alertas/predicciones. Vacio = sin avisos externos. Ver doc/NOTIFICACIONES.md"
  type        = string
  sensitive   = true
  default     = ""

  validation {
    condition     = var.telegram_bot_token == "" || can(regex("^[0-9]+:[A-Za-z0-9_-]+$", var.telegram_bot_token))
    error_message = "telegram_bot_token debe verse como 123456789:AAH... (el que entrega @BotFather)."
  }
}

variable "telegram_chat_ids" {
  description = "IDs de chat de Telegram que reciben los avisos, separados por coma y sin espacios"
  type        = string
  default     = ""

  validation {
    condition     = var.telegram_chat_ids == "" || can(regex("^-?[0-9]+(,-?[0-9]+)*$", var.telegram_chat_ids))
    error_message = "telegram_chat_ids: numeros separados por coma y sin espacios, p. ej. 7723097733,-100123456."
  }
}

variable "timezone" {
  description = "Zona horaria de la hora que aparece en los avisos de Telegram"
  type        = string
  default     = "America/Bogota"
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

variable "eip_address" {
  description = "IP elastica a RECUPERAR (una que ya liberaste y que el sensor tiene grabada en su programa). Vacia = AWS asigna una nueva. Cambiarla recrea la IP; el sensor solo llega si usa esa IP."
  type        = string
  default     = ""

  validation {
    condition     = var.eip_address == "" || can(regex("^([0-9]{1,3}[.]){3}[0-9]{1,3}$", var.eip_address))
    error_message = "eip_address debe ser una IPv4, p. ej. 23.20.62.1 (o vacia)."
  }
}

variable "disk_gb" {
  description = "Disco del sistema operativo (efimero: se recrea con la instancia)"
  type        = number
  default     = 12
}

variable "data_disk_gb" {
  description = "Disco de DATOS aparte (EBS): guarda las bases de datos e imagenes de Docker y SOBREVIVE a recrear la instancia"
  type        = number
  default     = 24
}

variable "availability_zone" {
  description = "Zona de disponibilidad (el disco de datos y la instancia deben estar en la misma). Vacia = la primera disponible"
  type        = string
  default     = ""
}

variable "crate_password" {
  description = "Password del usuario 'iot' de CrateDB (UI :4200, QuantumLeap, ETL, Grafana)"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.crate_password) >= 8 && can(regex("^[^'\"$\\\\`\\s]+$", var.crate_password)) && !startswith(var.crate_password, "CAMBIAR")
    error_message = "crate_password: minimo 8 caracteres, sin comillas, $, barra invertida ni espacios (rompen el .env) y distinta del texto CAMBIAR..."
  }
}

variable "proxmox_api_url" {
  description = "Адреса API Proxmox"
  type        = string
  default     = "https://192.168.5.200:8006/api2/json"
}

variable "proxmox_tls_insecure" {
  description = "Вимкнути перевірку TLS-сертифіката Proxmox"
  type        = bool
  default     = false
}

variable "target_node" {
  description = "Вузол Proxmox"
  type        = string
  default     = "pve"
}

variable "template_name" {
  description = "Шаблон cloud-init для клонування"
  type        = string
  default     = "ubuntu-24.04"
}

variable "storage_pool" {
  description = "Сховище для дисків ВМ"
  type        = string
  default     = "local-2TB"
}

variable "network_bridge" {
  description = "Мережевий міст Proxmox"
  type        = string
  default     = "vmbr0"
}

variable "gateway" {
  description = "Шлюз мережі 192.168.5.0/24"
  type        = string
  default     = "192.168.5.1"
}

variable "nameservers" {
  description = "DNS-сервери для ВМ"
  type        = string
  default     = "8.8.8.8 1.1.1.1"
}

variable "pool" {
  description = "Ресурсний пул команди в Proxmox"
  type        = string
  default     = null
}

variable "vm_user" {
  description = "Користувач cloud-init на ВМ"
  type        = string
  default     = "study7"
}

variable "ssh_public_key_path" {
  description = "Публічний SSH-ключ для входу на ВМ"
  type        = string
  default     = "~/.ssh/study7.pub"
}

variable "ssh_private_key_path" {
  description = "Приватний SSH-ключ для Ansible"
  type        = string
  default     = "~/.ssh/study7"
}

variable "nodes" {
  description = "Віртуальні машини команди Study7"
  type = map(object({
    role   = string
    ip     = string
    cores  = number
    memory = number
    disk   = string
  }))

  validation {
    condition     = alltrue([for n in values(var.nodes) : contains(["setup", "control_plane", "worker"], n.role)])
    error_message = "Роль вузла має бути setup, control_plane або worker."
  }

  validation {
    condition     = length([for n in values(var.nodes) : n if n.role == "control_plane"]) == 1
    error_message = "Потрібен рівно один вузол control_plane."
  }

  validation {
    condition     = alltrue([for n in values(var.nodes) : can(regex("^192\\.168\\.5\\.([2-9]|[1-9][0-9]|1[0-9][0-9]|2[0-4][0-9]|25[0-4])$", n.ip)) && n.ip != "192.168.5.200"])
    error_message = "IP-адреса має бути виділеною командою адресою в 192.168.5.0/24, не шлюзом і не Proxmox."
  }

  validation {
    condition     = alltrue([for n in values(var.nodes) : n.cores <= 2 && n.memory <= 2048])
    error_message = "Обмеження замовника: не більше 2 vCPU і 2048 МБ RAM на ВМ."
  }

  validation {
    condition     = alltrue([for n in values(var.nodes) : n.role != "control_plane" || (n.cores >= 2 && n.memory >= 2048)])
    error_message = "kubeadm вимагає для control plane щонайменше 2 vCPU і 2048 МБ RAM."
  }
}

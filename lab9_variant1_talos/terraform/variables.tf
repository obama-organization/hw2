variable "proxmox_endpoint" {
  description = "URL API Proxmox VE"
  type        = string
  default     = "https://192.168.5.200:8006/"
}

variable "proxmox_api_token" {
  description = "API-токен PVE у форматі user@realm!token-id=secret (задається через змінну середовища TF_VAR_proxmox_api_token)"
  type        = string
  sensitive   = true
}

variable "proxmox_insecure" {
  description = "Не перевіряти TLS-сертифікат PVE (самопідписаний у лабораторії)"
  type        = bool
  default     = true
}

variable "node_name" {
  description = "Вузол Proxmox, на якому створюються ВМ"
  type        = string
  default     = "pve"
}

variable "pool_id" {
  description = "Ресурсний пул команди в PVE (null — без пулу)"
  type        = string
  default     = null
}

variable "vm_datastore" {
  description = "Сховище для дисків ВМ і cloud-init"
  type        = string
  default     = "local-2TB"
}

variable "disk_format" {
  description = "Формат дисків: qcow2 для directory-сховища, raw для LVM/ZFS"
  type        = string
  default     = "qcow2"
}

variable "iso_datastore" {
  description = "Сховище з типом вмісту ISO, куди завантажується образ Talos"
  type        = string
  default     = "local"
}

variable "network_bridge" {
  type    = string
  default = "vmbr0"
}

variable "gateway" {
  type    = string
  default = "192.168.5.1"
}

variable "cidr_prefix" {
  type    = number
  default = 24
}

variable "dns_servers" {
  type    = list(string)
  default = ["8.8.8.8", "1.1.1.1"]
}

variable "cluster_name" {
  description = "Префікс імен ВМ і назва кластера"
  type        = string
  default     = "team7"
}

variable "talos_version" {
  type    = string
  default = "v1.14.6"
}

variable "talos_schematic_id" {
  description = "Image Factory schematic: офіційне розширення siderolabs/qemu-guest-agent"
  type        = string
  default     = "ce4c980550dd2ab1b17bbf2b08801c7eb59418eafe8f279833297925d67c7515"
}

variable "talos_iso_file_id" {
  description = "Якщо ISO Talos вже завантажене в PVE (напр. local:iso/talos.iso) — вкажіть його, і Terraform не завантажуватиме образ"
  type        = string
  default     = ""
}

variable "talos_platform" {
  description = "Платформа образу Talos: nocloud (IP з cloud-init) або metal (IP з DHCP на ВМ моніторингу, далі статичний)"
  type        = string
  default     = "nocloud"
  validation {
    condition     = contains(["nocloud", "metal"], var.talos_platform)
    error_message = "talos_platform: nocloud або metal."
  }
}

variable "talos_bios" {
  description = "Прошивка ВМ Talos: ovmf (UEFI, systemd-boot) або seabios. На SeaBIOS встановлений Talos 1.14 у лабораторії не завантажувався з диска"
  type        = string
  default     = "ovmf"
}

variable "talos_qemu_agent" {
  description = "Чи чекати на qemu-guest-agent у вузлах Talos (вимкніть для образів без агента, напр. стандартного metal ISO)"
  type        = bool
  default     = true
}

variable "talos_nodes" {
  description = "Вузли кластера Talos. data_disk > 0 додає другий диск під local-path-provisioner"
  type = map(object({
    role      = string
    ip        = string
    cores     = number
    memory    = number
    disk      = number
    data_disk = number
    vm_id     = optional(number)
    mac       = optional(string) # фіксований MAC: на ньому тримаються DHCP-оренда і статична адреса Talos
  }))
  default = {
    "cp-1" = { role = "controlplane", ip = "192.168.5.72", cores = 2, memory = 2048, disk = 20, data_disk = 0 }
    "w-1"  = { role = "worker", ip = "192.168.5.73", cores = 2, memory = 2048, disk = 20, data_disk = 10 }
    "w-2"  = { role = "worker", ip = "192.168.5.74", cores = 2, memory = 2048, disk = 20, data_disk = 10 }
  }

  validation {
    condition     = alltrue([for n in values(var.talos_nodes) : contains(["controlplane", "worker"], n.role)])
    error_message = "role має бути controlplane або worker."
  }
  validation {
    condition     = length([for n in values(var.talos_nodes) : n if n.role == "controlplane"]) >= 1
    error_message = "Потрібен хоча б один вузол controlplane."
  }
}

variable "mon_vm" {
  description = "ВМ з Vector, Loki, Prometheus, Alertmanager, Grafana і S3-сховищем для Velero"
  type = object({
    ip     = string
    cores  = number
    memory = number
    disk   = number
  })
  default = { ip = "192.168.5.71", cores = 2, memory = 2048, disk = 30 }
}

variable "ubuntu_template_name" {
  description = "Шаблон Ubuntu 24.04 з cloud-init для клонування"
  type        = string
  default     = "ubuntu-24.04"
}

variable "ubuntu_template_id" {
  description = "VMID шаблону (0 — знайти за назвою)"
  type        = number
  default     = 0
}

variable "admin_user" {
  description = "Користувач для Ansible на ВМ моніторингу (вхід лише за ключем)"
  type        = string
  default     = "ops"
}

variable "ssh_public_key_file" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    proxmox = {
      source  = "telmate/proxmox"
      version = "3.0.2-rc04"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

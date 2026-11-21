locals {
  talos_iso_url  = "https://factory.talos.dev/image/${var.talos_schematic_id}/${var.talos_version}/nocloud-amd64.iso"
  talos_iso_id   = var.talos_iso_file_id != "" ? var.talos_iso_file_id : proxmox_download_file.talos_iso[0].id
  ubuntu_tmpl_id = var.ubuntu_template_id != 0 ? var.ubuntu_template_id : data.proxmox_virtual_environment_vms.ubuntu_template[0].vms[0].vm_id

  controlplanes = { for k, v in var.talos_nodes : "${var.cluster_name}-${k}" => v if v.role == "controlplane" }
  workers       = { for k, v in var.talos_nodes : "${var.cluster_name}-${k}" => v if v.role == "worker" }
}

resource "proxmox_download_file" "talos_iso" {
  count = var.talos_iso_file_id == "" ? 1 : 0

  content_type        = "iso"
  datastore_id        = var.iso_datastore
  node_name           = var.node_name
  url                 = local.talos_iso_url
  file_name           = "talos-${var.talos_version}-nocloud-qga-amd64.iso"
  overwrite           = false
  overwrite_unmanaged = true
  upload_timeout      = 1800
}

resource "proxmox_virtual_environment_vm" "talos" {
  for_each = var.talos_nodes

  name        = "${var.cluster_name}-${each.key}"
  vm_id       = each.value.vm_id
  description = "Talos ${var.talos_version} (${each.value.role}). Керується Terraform, лаб. 9, варіант 1."
  node_name   = var.node_name
  pool_id     = var.pool_id
  tags        = sort(["terraform", "talos", var.cluster_name, each.value.role])

  on_boot         = true
  started         = true
  stop_on_destroy = true
  machine         = "q35"
  bios            = var.talos_bios
  scsi_hardware   = "virtio-scsi-single"

  dynamic "efi_disk" {
    for_each = var.talos_bios == "ovmf" ? [1] : []
    content {
      datastore_id      = var.vm_datastore
      file_format       = var.disk_format
      type              = "4m"
      pre_enrolled_keys = false
    }
  }

  cpu {
    cores = each.value.cores
    type  = "host"
  }

  memory {
    dedicated = each.value.memory
  }

  # Пристрій агента потрібен з першого запуску: інакше сервіс ext-qemu-guest-agent у Talos
  # чекає на /dev/virtio-ports/... і вузол назавжди лишається в стадії booting.
  # У maintenance mode (ISO) агента немає, тому чекаємо на нього недовго.
  agent {
    enabled = var.talos_qemu_agent
    trim    = true
    timeout = "2m"
  }

  disk {
    datastore_id = var.vm_datastore
    interface    = "scsi0"
    size         = each.value.disk
    file_format  = var.disk_format
    iothread     = true
    discard      = "on"
    ssd          = true
  }

  dynamic "disk" {
    for_each = each.value.data_disk > 0 ? [each.value.data_disk] : []
    content {
      datastore_id = var.vm_datastore
      interface    = "scsi1"
      size         = disk.value
      file_format  = var.disk_format
      iothread     = true
      discard      = "on"
      ssd          = true
    }
  }

  cdrom {
    file_id   = local.talos_iso_id
    interface = "ide3"
  }
  boot_order = ["scsi0", "ide3"]

  network_device {
    bridge      = var.network_bridge
    model       = "virtio"
    mac_address = each.value.mac
  }

  operating_system {
    type = "l26"
  }

  initialization {
    datastore_id = var.vm_datastore
    ip_config {
      ipv4 {
        address = "${each.value.ip}/${var.cidr_prefix}"
        gateway = var.gateway
      }
    }
    dns {
      servers = var.dns_servers
    }
  }

  lifecycle {
    ignore_changes = [cdrom]
  }
}

data "proxmox_virtual_environment_vms" "ubuntu_template" {
  count     = var.ubuntu_template_id == 0 ? 1 : 0
  node_name = var.node_name

  filter {
    name   = "name"
    values = [var.ubuntu_template_name]
  }
  filter {
    name   = "template"
    values = [true]
  }
}

resource "proxmox_virtual_environment_vm" "mon" {
  name        = "${var.cluster_name}-mon"
  description = "Vector, Loki, Prometheus, Alertmanager, Grafana, SeaweedFS S3 (Velero). Керується Terraform + Ansible."
  node_name   = var.node_name
  pool_id     = var.pool_id
  tags        = sort(["terraform", "ubuntu", var.cluster_name, "monitoring", "backup"])

  on_boot         = true
  started         = true
  stop_on_destroy = true

  clone {
    vm_id        = local.ubuntu_tmpl_id
    full         = true
    datastore_id = var.vm_datastore
  }

  cpu {
    cores = var.mon_vm.cores
    type  = "host"
  }

  memory {
    dedicated = var.mon_vm.memory
  }

  agent {
    enabled = true
  }

  disk {
    datastore_id = var.vm_datastore
    interface    = "scsi0"
    size         = var.mon_vm.disk
    file_format  = var.disk_format
    discard      = "on"
    ssd          = true
  }

  network_device {
    bridge = var.network_bridge
    model  = "virtio"
  }

  initialization {
    datastore_id = var.vm_datastore
    ip_config {
      ipv4 {
        address = "${var.mon_vm.ip}/${var.cidr_prefix}"
        gateway = var.gateway
      }
    }
    dns {
      servers = var.dns_servers
    }
    user_account {
      username = var.admin_user
      keys     = [trimspace(file(pathexpand(var.ssh_public_key_file)))]
    }
  }
}

resource "local_file" "ansible_inventory" {
  filename        = "${path.module}/../ansible/inventory/hosts.yml"
  file_permission = "0644"
  content = templatefile("${path.module}/templates/hosts.yml.tftpl", {
    cluster_name       = var.cluster_name
    talos_version      = var.talos_version
    talos_schematic_id = var.talos_schematic_id
    gateway            = var.gateway
    cidr_prefix        = var.cidr_prefix
    talos_platform     = var.talos_platform
    admin_user         = var.admin_user
    mon_name           = proxmox_virtual_environment_vm.mon.name
    mon_ip             = var.mon_vm.ip
    controlplanes      = local.controlplanes
    workers            = local.workers
    vm_ids             = { for k, vm in proxmox_virtual_environment_vm.talos : vm.name => vm.vm_id }
    macs               = { for k, vm in proxmox_virtual_environment_vm.talos : vm.name => vm.network_device[0].mac_address }
  })
}

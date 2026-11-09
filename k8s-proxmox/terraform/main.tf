resource "proxmox_vm_qemu" "node" {
  for_each = var.nodes

  name        = each.key
  target_node = var.target_node
  clone       = var.template_name
  pool        = var.pool
  tags        = "study7,terraform,kubernetes,${replace(each.value.role, "_", "-")}"
  onboot      = true

  agent   = 1
  os_type = "cloud-init"
  memory  = each.value.memory
  scsihw  = "virtio-scsi-pci"

  cpu {
    cores   = each.value.cores
    sockets = 1
    type    = "host"
  }

  disk {
    slot    = "ide2"
    type    = "cloudinit"
    storage = var.storage_pool
  }

  disk {
    slot    = "scsi0"
    size    = each.value.disk
    type    = "disk"
    storage = var.storage_pool
    format  = "qcow2"
  }

  network {
    id     = 0
    model  = "virtio"
    bridge = var.network_bridge
  }

  ipconfig0  = "ip=${each.value.ip}/24,gw=${var.gateway}"
  nameserver = var.nameservers
  ciuser     = var.vm_user
  sshkeys    = file(pathexpand(var.ssh_public_key_path))
  skip_ipv6  = true
}

resource "local_file" "ansible_inventory" {
  filename        = "${path.module}/../ansible/inventory/hosts.ini"
  file_permission = "0644"
  content = templatefile("${path.module}/templates/hosts.ini.tftpl", {
    nodes    = var.nodes
    user     = var.vm_user
    key_path = var.ssh_private_key_path
  })

  depends_on = [proxmox_vm_qemu.node]
}

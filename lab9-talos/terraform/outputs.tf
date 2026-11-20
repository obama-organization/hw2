output "talos_nodes" {
  description = "Вузли Talos: ім'я -> IP"
  value       = { for k, v in var.talos_nodes : "${var.cluster_name}-${k}" => v.ip }
}

output "mon_vm" {
  value = {
    name       = proxmox_virtual_environment_vm.mon.name
    ip         = var.mon_vm.ip
    grafana    = "http://${var.mon_vm.ip}:3000"
    prometheus = "http://${var.mon_vm.ip}:9090"
    alerts     = "http://${var.mon_vm.ip}:9093"
    s3         = "https://${var.mon_vm.ip}:8333"
  }
}

output "talos_iso" {
  value = local.talos_iso_id
}

output "nodes" {
  description = "Створені ВМ: ID у Proxmox, роль і адреса"
  value = {
    for name, vm in proxmox_vm_qemu.node : name => {
      vmid = vm.vmid
      role = var.nodes[name].role
      ip   = var.nodes[name].ip
    }
  }
}

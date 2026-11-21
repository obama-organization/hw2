#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

: "${TF_VAR_proxmox_api_token:?Задайте TF_VAR_proxmox_api_token=\"user@pve!token=secret\"}"

./scripts/preflight.sh

terraform -chdir=terraform init -input=false
terraform -chdir=terraform apply -input=false -auto-approve

cd ansible
ansible-playbook site.yml
ansible-playbook 90-verify.yml

echo
echo "Grafana:      http://$(terraform -chdir=../terraform output -json mon_vm | python3 -c 'import json,sys;print(json.load(sys.stdin)["ip"])'):3000  (admin / .state/secrets/grafana_admin_password)"
echo "kubeconfig:   $(cd .. && pwd)/.state/kubeconfig"
echo "talosconfig:  $(cd .. && pwd)/.state/talos/talosconfig"

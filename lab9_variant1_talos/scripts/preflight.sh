#!/usr/bin/env bash
set -uo pipefail

PVE=${PVE:-192.168.5.200}
IPS=${IPS:-"192.168.5.71 192.168.5.72 192.168.5.73 192.168.5.74"}
ok=1

printf "Proxmox API %s:8006 ... " "$PVE"
if curl -sk -m 5 -o /dev/null "https://$PVE:8006/"; then
  echo OK
else
  echo "НЕДОСТУПНИЙ (підключіть WireGuard зі своїм .conf)"
  echo "Без доступу до мережі лабораторії IP-адреси перевірити неможливо."
  exit 1
fi

if [[ -z "${TF_VAR_proxmox_api_token:-}" ]]; then
  echo "TF_VAR_proxmox_api_token не задано"; ok=0
else
  printf "API-токен ... "
  code=$(curl -sk -m 5 -o /dev/null -w '%{http_code}' -H "Authorization: PVEAPIToken=${TF_VAR_proxmox_api_token}" "https://$PVE:8006/api2/json/version")
  [[ "$code" == 200 ]] && echo OK || { echo "HTTP $code"; ok=0; }
fi

for ip in $IPS; do
  printf "IP %-15s ... " "$ip"
  if ping -c 1 -t 1 "$ip" >/dev/null 2>&1 || ping -c 1 -W 1 "$ip" >/dev/null 2>&1; then
    echo "ЗАЙНЯТА (відповідає на ping)"; ok=0
  else
    echo "вільна"
  fi
done

for t in terraform talosctl kubectl helm ansible-playbook; do
  command -v "$t" >/dev/null || { echo "Немає утиліти: $t"; ok=0; }
done

[[ $ok == 1 ]] && echo "Готово до розгортання." || { echo "Є проблеми, див. вище."; exit 1; }

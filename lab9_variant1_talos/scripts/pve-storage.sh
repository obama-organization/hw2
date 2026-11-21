#!/usr/bin/env bash
set -euo pipefail
: "${TF_VAR_proxmox_api_token:?Задайте TF_VAR_proxmox_api_token}"
API="https://192.168.5.200:8006/api2/json"
NODE="${PVE_NODE:-pve}"
H="Authorization: PVEAPIToken=${TF_VAR_proxmox_api_token}"
echo "== Сховища з типом iso =="
curl -sk -H "$H" "$API/nodes/$NODE/storage?content=iso" | python3 -c 'import json,sys; [print(s["storage"], s.get("type"), s.get("content")) for s in json.load(sys.stdin).get("data",[])]'
echo "== ISO-файли =="
for s in $(curl -sk -H "$H" "$API/nodes/$NODE/storage?content=iso" | python3 -c 'import json,sys; print(" ".join(s["storage"] for s in json.load(sys.stdin).get("data",[])))'); do
  curl -sk -H "$H" "$API/nodes/$NODE/storage/$s/content?content=iso" | python3 -c 'import json,sys; [print(v["volid"]) for v in json.load(sys.stdin).get("data",[])]'
done
echo "== Права токена на сховища =="
curl -sk -H "$H" "$API/access/permissions" | python3 -c 'import json,sys; d=json.load(sys.stdin).get("data",{}); [print(p, ",".join(k for k in v if "Datastore" in k)) for p,v in d.items() if p.startswith("/storage") or p=="/"]'

# Лабораторна 9, варіант 1 — Talos Linux у Proxmox: логування, моніторинг, runtime security, бекапи

Кластер Kubernetes на **Talos Linux** у PVE розгортається кодом: ВМ створює **Terraform**, налаштовує **Ansible**.

| Вимога варіанту | Як реалізовано |
|---|---|
| Кластер на Talos Linux | 1 control plane + 2 workers, Talos v1.14.6 (UEFI), інсталятор Image Factory з qemu-guest-agent |
| Vector — приймач логів ОС, далі в Loki | Talos шле логи сервісів (`machine.logging`) і ядра (`KmsgLogConfig`) по TCP у Vector на ВМ `mon`, Vector — у Loki |
| Metrics endpoint Talos → Prometheus | etcd `:2381` (`listen-metrics-urls`), kube-proxy `:10249`, controller-manager/scheduler `bind-address 0.0.0.0`, kubelet/cAdvisor, node-exporter `:9100` |
| Борди в Grafana | 5 дашбордів (`scripts/gen_dashboards.py`): вузли Talos, стан K8s, логи Talos, Falco+аудит, алерти+бекапи |
| Backup — Velero | Velero + node-agent (Kopia) → S3 (SeaweedFS) з TLS, SSE-S3 і Object Lock; розклади daily/hourly; тест відновлення |
| Falco → Loki → Grafana | Falco (modern eBPF) → falcosidekick → Loki (+ Alertmanager для Warning і вище) |
| kube-state-metrics | Helm-чарт, NodePort 30080, скрейпить Prometheus |
| Логи K8s — Vector | Vector-агент (DaemonSet): логи подів і аудит kube-apiserver → Vector-агрегатор → Loki |
| VM через Terraform і Ansible в PVE | `terraform/` (провайдер bpg/proxmox), `ansible/` (ролі) |
| Хоча б один алерт надходить | Alertmanager → webhook → Vector → Loki (завжди) і Telegram (якщо задано токен); тест `90-verify.yml` |

## Архітектура

```
                       Proxmox VE (192.168.5.200), міст vmbr0, мережа 192.168.5.0/24
 ┌───────────────────────────── Talos Linux ─────────────────────────────┐   ┌──────────── team7-mon (Ubuntu 24.04) ────────────┐
 │ team7-cp-1 .72      team7-w-1 .73        team7-w-2 .74                 │   │ 192.168.5.71, Docker Compose, UFW               │
 │  etcd :2381 ─────────────────────────────────────────── metrics ───────┼──▶│ Prometheus :9090 ──▶ Alertmanager :9093          │
 │  node-exporter :9100, kubelet :10250, kube-proxy :10249  (скрейп)      │   │        │ правила              │ webhook / Telegram │
 │  kube-state-metrics NodePort :30080, Velero metrics :30085             │   │        ▼                      ▼                    │
 │  machined/kubelet/etcd логи ── tcp/6051 ───────────────────────────────┼──▶│ Vector-агрегатор ───────────▶ Loki :3100         │
 │  ядро (kmsg) ───────────────── tcp/6050 ───────────────────────────────┼──▶│   ▲ tcp/6000 (агенти)                ▲           │
 │  Vector-агент (поди + аудит API) ──────────────────────────────────────┼───┘                                     │           │
 │  Falco (eBPF) ─▶ falcosidekick ─────────── Loki / Alertmanager ────────┼────────────────────────────────────────┘           │
 │  Velero + node-agent (Kopia) ───────────── HTTPS S3 :8333 ─────────────┼──▶│ SeaweedFS S3: TLS, SSE-S3, Object Lock (7 днів)   │
 └────────────────────────────────────────────────────────────────────────┘   │ Grafana :3000 (Prometheus, Loki, Alertmanager)   │
                                                                              └──────────────────────────────────────────────────┘
```

Чому моніторинг і бекапи на окремій ВМ: логи, алерти і копії переживають аварію кластера, а вузли Talos (≤ 2 ГБ RAM) не перевантажені Prometheus/Loki/Grafana.

## Що потрібно

- WireGuard-тунель до лабораторії (свій `.conf`, мережі 192.168.5.0/24 і 192.168.10.0/24).
- `terraform` ≥ 1.5, `ansible` ≥ 2.16 (колекції `kubernetes.core`, `community.general`, `ansible.posix`), `talosctl` 1.14, `kubectl`, `helm`.
- API-токен PVE з правами на створення ВМ, сховище `local-2TB` (диски) і `local` (ISO), міст `vmbr0`.
- SSH-ключ `~/.ssh/id_ed25519.pub` (для ВМ моніторингу; пароль у cloud-init не задається).

## Запуск

Токен PVE задається лише змінною середовища, у файли його не записуйте:

```bash
export TF_VAR_proxmox_api_token='tf-team-7@pve!terraform-token=<secret>'
```

Алерти в Telegram необов'язкові. Без цих змінних алерти все одно доходять у Loki і видні в Grafana:

```bash
export TG_BOT_TOKEN='<bot token>' TG_CHAT_ID='<chat id>'
```

Значення за замовчуванням (IP, сховища, ресурси ВМ) задані у `terraform/variables.tf`. Щоб їх змінити, скопіюйте `terraform/terraform.tfvars.example` у `terraform/terraform.tfvars`. Якщо токен обмежено пулом команди, додайте туди `pool_id = "tf-team-7"`. Якщо ISO Talos уже завантажене в PVE, вкажіть `talos_iso_file_id = "local:iso/<файл>.iso"`, і Terraform не завантажуватиме образ.

`preflight.sh` перевіряє VPN, токен і чи вільні IP. `deploy.sh` запускає preflight, `terraform apply`, `ansible-playbook site.yml` і `90-verify.yml`:

```bash
./scripts/preflight.sh
./scripts/deploy.sh
```

Покроково:

```bash
terraform -chdir=terraform init && terraform -chdir=terraform apply
cd ansible
ansible-playbook 10-monitoring-host.yml
ansible-playbook 20-talos-cluster.yml
ansible-playbook 30-k8s-platform.yml
ansible-playbook 40-velero.yml
ansible-playbook 90-verify.yml
ansible-playbook 91-restore-test.yml
```

| Крок | Що робить |
|---|---|
| `terraform apply` | 4 ВМ і інвентар для Ansible |
| `10-monitoring-host.yml` | Ubuntu: харденінг, Docker, Vector, Loki, Prometheus, Alertmanager, Grafana, S3 |
| `20-talos-cluster.yml` | `talosctl gen config`, apply-config, bootstrap, kubeconfig, перевірка стану |
| `30-k8s-platform.yml` | PSA, local-path, node-exporter, kube-state-metrics, Vector-агент, Falco |
| `40-velero.yml` | Velero, розклади, тестовий застосунок, перший бекап |
| `90-verify.yml` | логи, метрики, Falco і реальний алерт KubePodCrashLooping |
| `91-restore-test.yml` | видаляє namespace `demo` і відновлює його з бекапу |

Доступ: Grafana `http://192.168.5.71:3000` (admin / `.state/secrets/grafana_admin_password`),
`export KUBECONFIG=$PWD/.state/kubeconfig TALOSCONFIG=$PWD/.state/talos/talosconfig`.

## Безпека (що зроблено)

- **Talos**: немає SSH/shell, API лише через mTLS; PSA `baseline` за замовчуванням, `restricted` для застосунку, `privileged` лише для системних агентів; sysctl-харденінг; шифрування Secrets в etcd (secretbox); аудит API з фільтрацією шуму.
- **ВМ моніторингу**: вхід лише за ключем, без root і паролів, fail2ban, UFW (доступ тільки з 192.168.5.0/24 і VPN), автоматичні оновлення безпеки, sysctl; контейнери з `no-new-privileges` і лімітами пам'яті.
- **Бекапи**: TLS до S3 з перевіркою сертифіката (caCert у Velero), шифрування на диску SSE-S3 (ключ `.state/secrets/s3_sse_kek`), Object Lock GOVERNANCE 7 днів (видалити версію бекапу неможливо), Kopia-репозиторій зашифрований власним паролем (а не стандартним).
- **Секрети** не потрапляють у Git: `.state/` і `*.tfvars` у `.gitignore`, токен PVE — лише змінна середовища.

> Збережіть копію `.state/` (особливо `talos/secrets.yaml`, `secrets/s3_sse_kek`, `secrets/velero_repo_password`): без них не відновити доступ до кластера і бекапів.

## Розгорнуто в лабораторії (21.11.2026)

ВМ у PVE: `team7-mon` (108, .71), `team7-cp-1` (109, .72), `team7-w-1` (114, .73), `team7-w-2` (113, .74).

- Кластер Talos v1.14.6 / Kubernetes v1.37.1: 3 вузли Ready, `talosctl health` проходить, повний перезапуск ВМ (`reboot --mode powercycle`) завантажує систему з диска.
- Логи ОС Talos (ядро і сервіси всіх 3 вузлів), подів і аудиту API — у Loki; 24 з 24 цілей Prometheus `up`.
- Falco спрацьовує на власні й стандартні правила; події — у Loki і Alertmanager.
- `90-verify.yml`: алерт **KubePodCrashLooping** і алерти Falco доставлені (Alertmanager → webhook → Vector → Loki).
- Velero: бекап `lab9-baseline` — `Completed`, 616 об'єктів, том PVC застосунку demo через Kopia; S3 з TLS, SSE-S3 і Object Lock.

## Особливості лабораторного PVE (і як вони враховані в коді)

| Що виявилось | Що зроблено |
|---|---|
| Токен не має `Datastore.AllocateTemplate` — завантажити ISO неможливо | використано наявний `local:iso/metal-amd64.iso` (`talos_iso_file_id`), інсталятор — `factory.talos.dev/metal-installer/<schematic з qemu-guest-agent>` (`talos_platform = "metal"`) |
| У мережі 192.168.5.0/24 немає DHCP, metal ISO ігнорує cloud-init | роль `talos_dhcp`: dnsmasq на `team7-mon` відповідає **лише** MAC-адресам наших ВМ (MAC зафіксовано в Terraform); після встановлення Talos має статичну адресу (`LinkAliasConfig` за MAC + `LinkConfig`) |
| На SeaBIOS встановлений Talos не завантажувався з диска | ВМ Talos на OVMF (UEFI) з EFI-диском (`talos_bios = "ovmf"`) |
| З двома дисками на virtio-scsi-single імена `sda`/`sdb` міняються між завантаженнями → Talos встановлювався не на той диск і перевстановлювався з ISO поверх EPHEMERAL | диски вибираються за розміром: системний `disk.size > 15u * GB`, диск даних `!system_disk && disk.size <= 15u * GB` |
| Без пристрою qemu-agent вузол назавжди в стадії `booting` (сервіс `ext-qemu-guest-agent` чекає `/dev/virtio-ports/...`) | агент увімкнено з першого запуску ВМ, Terraform чекає на нього лише 2 хв |
| Сховище `local-2TB` дуже повільне (fsync 0,3–3,5 с): API Server не проходив перевірку etcd, controller-manager падав | `talos_slow_storage_tuning`: etcd `unsafe-no-fsync`, без виборів лідера в controller-manager і scheduler (один control plane), тайм-аути перевірки etcd 10 с; Grafana — SQLite у режимі WAL; довші очікування в ролях |
| Диск ВМ моніторингу 30 ГБ, а розділ шаблону — 18 ГБ | роль `base_hardening` розширює розділ, PV і LV на весь диск |
| SeaweedFS працює від uid 1000 і не міг прочитати ключі; на малому диску не створював томи | власник секретів — uid 1000; томи по 512 МБ, `-volume.max=40` |
| node-agent Velero не працює на control plane | бекап томів за анотацією `backup.velero.io/backup-volumes` (opt-in) |
| На control plane (2 ГБ) лишається ~110 Mi для запитів | Falco запитує 64 Mi (ліміт 512 Mi) |

Terraform запускати з `-parallelism=1`: паралельне створення ВМ на `local-2TB` впирається в блокування сховища.

## Перевірено також локально

- `terraform validate`, `ansible-playbook --syntax-check`, `talosctl validate --mode metal`, `helm template` для всіх чартів, `falco -V` для власних правил.
- Стек ВМ моніторингу в Docker: 18 правил Prometheus, 54 запити дашбордів, S3 з TLS/SSE/Object Lock (`AccessDenied` на видалення заблокованої версії).
- Ролі Kubernetes, Velero і обидва тестові плейбуки — на k3s у Docker.

## Структура

```
terraform/   ВМ у PVE: Talos ×3 (ISO з Image Factory, cloud-init IP), Ubuntu mon (клон шаблону), inventory
ansible/
  roles/base_hardening       SSH, UFW, fail2ban, sysctl, unattended-upgrades, swap
  roles/docker_engine        Docker + Compose v2
  roles/observability_stack  Vector, Loki, Prometheus (+правила), Alertmanager, Grafana (+дашборди), SeaweedFS S3
  roles/talos_cluster        патчі машинної конфігурації, apply-config, bootstrap, kubeconfig
  roles/k8s_platform         PSA, local-path, node-exporter, kube-state-metrics, Vector-агент, Falco
  roles/velero_backup        Velero, розклади, demo-застосунок, перший бекап
scripts/     preflight.sh, deploy.sh, gen_dashboards.py
```

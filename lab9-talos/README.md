# Лабораторна 9, варіант 1 — Talos Linux у Proxmox: логування, моніторинг, runtime security, бекапи

Кластер Kubernetes на **Talos Linux** у PVE розгортається кодом: ВМ створює **Terraform**, налаштовує **Ansible**.

| Вимога варіанту | Як реалізовано |
|---|---|
| Кластер на Talos Linux | 1 control plane + 2 workers, Talos v1.14.6, образ Image Factory (nocloud + qemu-guest-agent) |
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

## Що вже перевірено (без доступу до лабораторії)

- `terraform validate`, `terraform fmt -check`; `ansible-playbook --syntax-check`; `talosctl validate --mode metal` для всіх патчів Talos 1.14.
- Стек ВМ моніторингу запускався локально в Docker: Vector приймає логи у форматі Talos (сервіси і ядро) і пише в Loki, 18 правил Prometheus без помилок, 5 дашбордів (54 запити PromQL/LogQL парсяться), алерт доходить через webhook у Loki.
- S3 (SeaweedFS): TLS-only, SSE-S3 (AES256), Object Lock — видалення заблокованої версії отримує `AccessDenied`.
- Ролі `k8s_platform`, `velero_backup`, `90-verify.yml`, `91-restore-test.yml` пройшли на k3s у Docker: усі цілі Prometheus `up`, логи подів і аудиту в Loki, Falco → Loki + Alertmanager, бекап `Completed` (399 об'єктів, том PVC через Kopia), відновлення namespace з тими самими даними, алерт KubePodCrashLooping доставлено.
- Talos у Docker Desktop (Mac) не запускається (обмеження ядра linuxkit), тому установка Talos на ВМ PVE перевіряється лише в лабораторії.

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

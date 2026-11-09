# Інфраструктура Study7: Kubernetes у Proxmox

Terraform створює в Proxmox 4 віртуальні машини, Ansible встановлює на них Kubernetes: один вузол control plane, два робочі вузли й окремий хост керування. Ресурси відповідають погодженому [запиту на ресурси](https://claude.ai/artifact/LLQYPoWeYSXHWBJDjiHrVZ).

```
k8s-proxmox/
├── terraform/      ВМ у Proxmox і генерація інвентаря Ansible
├── ansible/        налаштування ОС, containerd, kubeadm, Calico
└── k8s/base/       простір імен застосунку з Pod Security і NetworkPolicy
```

Перевірки Shift-Left у CI лежать у `.github/workflows/infra-security.yml` у корені репозиторію: GitHub запускає workflow лише звідти.

| ВМ | IP | Роль | vCPU | RAM | Диск |
| --- | --- | --- | --- | --- | --- |
| Study7-k8s-setup | 192.168.5.71 | хост керування, kubectl | 1 | 1 ГБ | 20 ГБ |
| Study7-k8s-cp | 192.168.5.72 | control plane | 2 | 2 ГБ | 30 ГБ |
| Study7-k8s-w1 | 192.168.5.73 | робочий вузол | 2 | 2 ГБ | 30 ГБ |
| Study7-k8s-w2 | 192.168.5.74 | робочий вузол | 2 | 2 ГБ | 30 ГБ |

Версії: Ubuntu 24.04, Kubernetes 1.37, containerd 2.2, Calico 3.33 (VXLAN), провайдер telmate/proxmox 3.0.2-rc04. Мережа подів — 10.244.0.0/16, сервісів — 10.96.0.0/12.

## Підготовка (один раз)

1. Підключіть VPN: `sudo wg-quick up ~/Downloads/study7-devops.conf`.
2. Встановіть Ansible (Terraform 1.5+ має бути вже встановлений): `brew install ansible`.
3. Створіть SSH-ключ для ВМ: `ssh-keygen -t ed25519 -f ~/.ssh/study7 -C study7`.
4. Скопіюйте `terraform/terraform.tfvars.example` у `terraform/terraform.tfvars`. Адреси в ньому команда вибрала сама з вільних: 5 листопада 2026 року 192.168.5.71–74 не відповідали ні на ping, ні на типові TCP-порти і не були вказані в налаштуваннях жодної ВМ у Proxmox. Файл `terraform.tfvars` у Git не потрапляє.

## Розгортання

Токен Proxmox передається тільки через змінні середовища, у файлах репозиторію його немає. Команди нижче читають його з `token.txt`, не виводячи на екран:

```bash
export PM_API_TOKEN_ID="$(sed -n 1p ~/Downloads/token.txt | tr -d '\r')"
export PM_API_TOKEN_SECRET="$(sed -n 2p ~/Downloads/token.txt | tr -d '\r')"
```

У Proxmox самопідписаний сертифікат. Доки замовник не надасть кореневий сертифікат, перевірку TLS доводиться вимикати на час сесії:

```bash
export TF_VAR_proxmox_tls_insecure=true
```

Створення ВМ:

```bash
cd k8s-proxmox/terraform
terraform init
terraform plan -out=study7.tfplan
terraform apply -parallelism=1 study7.tfplan
```

`-parallelism=1` клонує ВМ з шаблону по черзі, щоб вони не впиралися в блокування шаблону.

Terraform перевіряє вхідні дані до звернення до Proxmox: не більше 2 vCPU і 2 ГБ на ВМ, рівно один control plane з 2 vCPU і 2 ГБ, адреси лише з 192.168.5.0/24, крім шлюзу і самого Proxmox. Після `apply` він сам записує інвентар `ansible/inventory/hosts.ini`.

Встановлення Kubernetes:

```bash
cd ../ansible
ansible-galaxy collection install -r requirements.yml
ansible-playbook site.yml
```

Перевірка з хоста керування:

```bash
ssh -i ~/.ssh/study7 study7@<IP Study7-k8s-setup>
kubectl get nodes -o wide
```

Усі три вузли мають бути в стані `Ready`.

Видалення всіх ВМ команди: `terraform destroy` у каталозі `k8s-proxmox/terraform`.

## Відомі проблеми і що робити

| Симптом | Причина | Що робити |
| --- | --- | --- |
| Terraform: `read: connection reset by peer` | VPN обриває довгі запити до API Proxmox | Повторити `plan` і `apply`; якщо ВМ створилась, але позначена `tainted`, виконати `terraform untaint 'proxmox_vm_qemu.node["<ім'я>"]'` |
| Terraform: `qemu-img resize ... got timeout` | Повільне сховище local-2TB | Повторити `plan` і `apply` |
| У плані диски `scsi0` і `ide2` міняються місцями | Блоки `disk` записані не в тому порядку, в якому їх читає провайдер | Не застосовувати план; в `main.tf` диск `ide2` має йти першим |
| Ansible: `Unable to acquire the dpkg frontend lock` | На свіжих ВМ працює автооновлення Ubuntu | Повторити плейбук; apt чекає блокування до 10 хвилин |
| etcd: `slow fdatasync`, перезапуски controller-manager і scheduler | Запис на диск триває понад 1 с | Вибори лідера на єдиному control plane вимкнено; плейбук можна запускати повторно |

Плейбук ідемпотентний: повторний запуск пропускає вже виконані кроки.

## Безпека

| Етап | Що перевіряється | Інструмент | Де |
| --- | --- | --- | --- |
| Коміт | секрети в коді та історії | gitleaks | pre-commit і CI |
| Terraform | формат, синтаксис, обмеження ресурсів | terraform fmt, validate | CI |
| Terraform, маніфести | небезпечні налаштування | Trivy config | CI, звіт у GitHub Security |
| Ansible | небезпечні модулі й практики | ansible-lint, профіль production | CI |
| Кожна зміна | перегляд іншим учасником | pull request | GitHub |

- Секрети не зберігаються в репозиторії: `*.tfvars`, `*.tfstate`, `token.txt`, `study7-*.conf`, `hosts.ini` і kubeconfig внесено в `.gitignore`.
- На ВМ вхід лише за SSH-ключем: пароль cloud-init не задається, вхід root і паролем вимкнено.
- Kubeconfig адміністратора є лише на control plane і хості керування, з правами `0600`.
- Простір імен `study7-app` працює з Pod Security рівня `restricted`, а NetworkPolicy за замовчуванням забороняє весь трафік, крім DNS.

Перевірити локально перед пушем:

```bash
terraform -chdir=k8s-proxmox/terraform fmt -check -recursive
terraform -chdir=k8s-proxmox/terraform validate
cd k8s-proxmox/ansible && ansible-lint site.yml
```

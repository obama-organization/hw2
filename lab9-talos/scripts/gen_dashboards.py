#!/usr/bin/env python3
import json
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "ansible/roles/observability_stack/files/dashboards"
PROM = {"type": "prometheus", "uid": "prometheus"}
LOKI = {"type": "loki", "uid": "loki"}


class Board:
    def __init__(self, uid, title, tags, variables=None, refresh="30s", time_from="now-3h"):
        self.uid, self.title, self.tags = uid, title, tags
        self.variables = variables or []
        self.refresh, self.time_from = refresh, time_from
        self.panels, self.y, self.next_id = [], 0, 1
        self.row_x, self.row_h = 0, 0

    def _place(self, w, h):
        if self.row_x + w > 24:
            self.y += self.row_h
            self.row_x, self.row_h = 0, 0
        pos = {"x": self.row_x, "y": self.y, "w": w, "h": h}
        self.row_x += w
        self.row_h = max(self.row_h, h)
        return pos

    def row(self, title):
        if self.row_x:
            self.y += self.row_h
            self.row_x, self.row_h = 0, 0
        self.panels.append({"type": "row", "title": title, "id": self.next_id, "collapsed": False,
                            "gridPos": {"x": 0, "y": self.y, "w": 24, "h": 1}, "panels": []})
        self.next_id += 1
        self.y += 1

    def add(self, panel, w, h):
        panel["id"] = self.next_id
        self.next_id += 1
        panel["gridPos"] = self._place(w, h)
        self.panels.append(panel)

    def dump(self):
        return {
            "uid": self.uid, "title": self.title, "tags": self.tags,
            "timezone": "browser", "editable": False, "graphTooltip": 1,
            "schemaVersion": 39, "version": 1, "refresh": self.refresh,
            "time": {"from": self.time_from, "to": "now"},
            "templating": {"list": self.variables},
            "annotations": {"list": []},
            "panels": self.panels,
        }


def tgt(ds, expr, legend="", instant=False, fmt=None, ref="A"):
    t = {"datasource": ds, "expr": expr, "refId": ref, "legendFormat": legend}
    if instant:
        t["instant"], t["range"] = True, False
    else:
        t["range"] = True
    if fmt:
        t["format"] = fmt
    return t


def stat(title, ds, expr, unit="short", thresholds=None, desc="", decimals=None):
    steps = thresholds or [{"color": "green", "value": None}]
    p = {"type": "stat", "title": title, "description": desc, "datasource": ds,
         "targets": [tgt(ds, expr, instant=True)],
         "fieldConfig": {"defaults": {"unit": unit, "thresholds": {"mode": "absolute", "steps": steps}},
                         "overrides": []},
         "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                     "colorMode": "background", "graphMode": "none", "textMode": "auto", "justifyMode": "center"}}
    if decimals is not None:
        p["fieldConfig"]["defaults"]["decimals"] = decimals
    return p


def ts(title, ds, targets, unit="short", desc="", stack=False, maxv=None, draw="line"):
    custom = {"drawStyle": draw, "lineWidth": 1, "fillOpacity": 15, "showPoints": "never",
              "stacking": {"mode": "normal" if stack else "none", "group": "A"}}
    d = {"unit": unit, "custom": custom}
    if maxv is not None:
        d["max"] = maxv
        d["min"] = 0
    return {"type": "timeseries", "title": title, "description": desc, "datasource": ds,
            "targets": targets, "fieldConfig": {"defaults": d, "overrides": []},
            "options": {"legend": {"displayMode": "table", "placement": "right", "calcs": ["lastNotNull", "max"]},
                        "tooltip": {"mode": "multi", "sort": "desc"}}}


def logs(title, expr, desc=""):
    return {"type": "logs", "title": title, "description": desc, "datasource": LOKI,
            "targets": [{"datasource": LOKI, "expr": expr, "refId": "A", "queryType": "range"}],
            "options": {"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending",
                        "enableLogDetails": True, "dedupStrategy": "none", "prettifyLogMessage": False}}


def table(title, ds, expr, desc="", hide=None, rename=None):
    excl = {c: True for c in (hide or [])}
    return {"type": "table", "title": title, "description": desc, "datasource": ds,
            "targets": [tgt(ds, expr, instant=True, fmt="table")],
            "transformations": [{"id": "organize", "options": {"excludeByName": excl,
                                                               "renameByName": rename or {}}}],
            "fieldConfig": {"defaults": {}, "overrides": []}, "options": {"showHeader": True}}


def bargauge(title, ds, expr, legend, desc=""):
    return {"type": "bargauge", "title": title, "description": desc, "datasource": ds,
            "targets": [tgt(ds, expr, legend=legend, instant=True)],
            "fieldConfig": {"defaults": {"unit": "short", "thresholds": {"mode": "absolute", "steps": [
                {"color": "blue", "value": None}]}}, "overrides": []},
            "options": {"orientation": "horizontal", "displayMode": "gradient", "showUnfilled": True,
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}}}


def qvar(name, label, ds, query, multi=True):
    return {"name": name, "label": label, "type": "query", "datasource": ds,
            "query": query if ds is PROM else {"label": query[1], "stream": query[0], "type": 1, "refId": "v"},
            "definition": query if ds is PROM else "", "refresh": 2, "includeAll": True, "multi": multi,
            "allValue": ".*", "current": {"selected": True, "text": ["All"], "value": ["$__all"]}, "sort": 1}


def cvar(name, label, options):
    return {"name": name, "label": label, "type": "custom", "query": ",".join(options), "includeAll": True,
            "multi": True, "allValue": ".*", "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
            "options": []}


RED_IF_ZERO = [{"color": "red", "value": None}, {"color": "green", "value": 1}]
RED_IF_ANY = [{"color": "green", "value": None}, {"color": "red", "value": 1}]

b = Board("lab9-talos-nodes", "Talos — вузли (ОС, etcd, API)", ["lab9", "talos", "prometheus"],
          [qvar("node", "Вузол", PROM, 'label_values(up{job="talos-node-exporter"}, node)')])
b.row("Огляд")
b.add(stat("Вузли online", PROM, 'sum(up{job="talos-node-exporter"})', thresholds=RED_IF_ZERO,
           desc="node-exporter відповідає на вузлах Talos"), 4, 4)
b.add(stat("etcd має лідера", PROM, 'min(etcd_server_has_leader)', thresholds=RED_IF_ZERO), 4, 4)
b.add(stat("Вузли Ready (K8s)", PROM, 'sum(kube_node_status_condition{condition="Ready",status="true"})',
           thresholds=RED_IF_ZERO), 4, 4)
b.add(stat("Активні алерти", PROM, 'count(ALERTS{alertstate="firing",alertname!="MonitoringHeartbeat"}) or vector(0)',
           thresholds=RED_IF_ANY), 4, 4)
b.add(stat("Логи Talos, рядків/хв", PROM,
           'sum(rate(vector_component_received_events_total{component_id=~"talos_kernel|talos_service"}[5m])) * 60',
           decimals=0, thresholds=RED_IF_ZERO, desc="Скільки рядків логів ОС Talos отримує Vector"), 4, 4)
b.add(stat("Uptime мінімальний", PROM, 'min(time() - node_boot_time_seconds{job="talos-node-exporter"})', unit="s"),
      4, 4)
b.row("Ресурси вузлів")
b.add(ts("CPU, %", PROM, [tgt(PROM, '100 - avg by (node) (rate(node_cpu_seconds_total{job="talos-node-exporter",mode="idle",node=~"$node"}[$__rate_interval])) * 100', "{{node}}")],
         unit="percent", maxv=100), 12, 8)
b.add(ts("Пам'ять, %", PROM, [tgt(PROM, '(1 - node_memory_MemAvailable_bytes{job="talos-node-exporter",node=~"$node"} / node_memory_MemTotal_bytes{job="talos-node-exporter",node=~"$node"}) * 100', "{{node}}")],
         unit="percent", maxv=100), 12, 8)
b.add(ts("Диск EPHEMERAL (/var), %", PROM, [tgt(PROM, '(1 - node_filesystem_avail_bytes{job="talos-node-exporter",mountpoint="/var",node=~"$node"} / node_filesystem_size_bytes{job="talos-node-exporter",mountpoint="/var",node=~"$node"}) * 100', "{{node}}")],
         unit="percent", maxv=100), 8, 8)
b.add(ts("Мережа, байт/с", PROM, [
    tgt(PROM, 'sum by (node) (rate(node_network_receive_bytes_total{job="talos-node-exporter",device!~"lo|veth.*|flannel.*|cni.*",node=~"$node"}[$__rate_interval]))', "rx {{node}}", ref="A"),
    tgt(PROM, '-sum by (node) (rate(node_network_transmit_bytes_total{job="talos-node-exporter",device!~"lo|veth.*|flannel.*|cni.*",node=~"$node"}[$__rate_interval]))', "tx {{node}}", ref="B")],
    unit="Bps"), 8, 8)
b.add(ts("Load average (1m)", PROM, [tgt(PROM, 'node_load1{job="talos-node-exporter",node=~"$node"}', "{{node}}")]), 8, 8)
b.row("etcd і API Server (metrics endpoints Talos)")
b.add(ts("etcd: розмір БД", PROM, [tgt(PROM, 'etcd_mvcc_db_total_size_in_bytes', "{{node}}")], unit="bytes"), 8, 8)
b.add(ts("etcd: fsync WAL p99", PROM, [tgt(PROM, 'histogram_quantile(0.99, sum by (le, node) (rate(etcd_disk_wal_fsync_duration_seconds_bucket[$__rate_interval])))', "{{node}}")],
         unit="s"), 8, 8)
b.add(ts("API Server: запити за кодом", PROM, [tgt(PROM, 'sum by (code) (rate(apiserver_request_total[$__rate_interval]))', "{{code}}")],
         unit="reqps", stack=True), 8, 8)
b.add(ts("API Server: 401/403 (спроби несанкціонованого доступу)", PROM,
         [tgt(PROM, 'sum by (code) (rate(apiserver_request_total{code=~"401|403"}[$__rate_interval]))', "{{code}}")],
         unit="reqps"), 12, 8)
b.add(ts("kube-proxy: синхронізація правил p99", PROM,
         [tgt(PROM, 'histogram_quantile(0.99, sum by (le, node) (rate(kubeproxy_sync_proxy_rules_duration_seconds_bucket[$__rate_interval])))', "{{node}}")],
         unit="s"), 12, 8)
BOARDS = [b]

b = Board("lab9-k8s-state", "Kubernetes — стан кластера (kube-state-metrics)", ["lab9", "kubernetes", "prometheus"],
          [qvar("namespace", "Namespace", PROM, 'label_values(kube_pod_info, namespace)')])
b.row("Огляд")
b.add(stat("Вузли Ready", PROM, 'sum(kube_node_status_condition{condition="Ready",status="true"})', thresholds=RED_IF_ZERO), 4, 4)
b.add(stat("Поди Running", PROM, 'sum(kube_pod_status_phase{phase="Running"})'), 4, 4)
b.add(stat("Поди не Running", PROM, 'sum(kube_pod_status_phase{phase=~"Pending|Failed|Unknown"}) or vector(0)', thresholds=RED_IF_ANY), 4, 4)
b.add(stat("Рестарти за 1 год", PROM, 'sum(increase(kube_pod_container_status_restarts_total[1h])) or vector(0)',
           decimals=0, thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 1}, {"color": "red", "value": 10}]), 4, 4)
b.add(stat("Deployment з недоступними репліками", PROM, 'count(kube_deployment_status_replicas_unavailable > 0) or vector(0)',
           thresholds=RED_IF_ANY), 4, 4)
b.add(stat("PVC Bound", PROM, 'sum(kube_persistentvolumeclaim_status_phase{phase="Bound"}) or vector(0)'), 4, 4)
b.row("Поди і робочі навантаження")
b.add(ts("Поди за фазою", PROM, [tgt(PROM, 'sum by (phase) (kube_pod_status_phase{namespace=~"$namespace"})', "{{phase}}")], stack=True), 12, 8)
b.add(bargauge("Топ-10 подів за рестартами (1 год)", PROM,
               'topk(10, sum by (namespace, pod) (increase(kube_pod_container_status_restarts_total{namespace=~"$namespace"}[1h])))',
               "{{namespace}}/{{pod}}"), 12, 8)
b.add(table("Deployments: доступно реплік, %", PROM,
            'sum by (namespace, deployment) (kube_deployment_status_replicas_available{namespace=~"$namespace"}) / sum by (namespace, deployment) (kube_deployment_spec_replicas{namespace=~"$namespace"}) * 100',
            hide=["Time"], rename={"Value": "Доступно, %"}), 12, 8)
b.add(table("Контейнери в стані очікування", PROM,
            'sum by (namespace, pod, container, reason) (kube_pod_container_status_waiting_reason{namespace=~"$namespace"}) > 0',
            hide=["Time", "Value"]), 12, 8)
b.row("Ресурси (cAdvisor + requests/limits)")
b.add(ts("CPU за namespace, ядер", PROM, [tgt(PROM, 'sum by (namespace) (rate(container_cpu_usage_seconds_total{container!="",namespace=~"$namespace"}[$__rate_interval]))', "{{namespace}}")],
         stack=True), 12, 8)
b.add(ts("Пам'ять за namespace", PROM, [tgt(PROM, 'sum by (namespace) (container_memory_working_set_bytes{container!="",namespace=~"$namespace"})', "{{namespace}}")],
         unit="bytes", stack=True), 12, 8)
b.add(ts("Requests пам'яті / allocatable вузла, %", PROM, [tgt(PROM, 'sum by (node) (kube_pod_container_resource_requests{resource="memory"}) / sum by (node) (kube_node_status_allocatable{resource="memory"}) * 100', "{{node}}")],
         unit="percent", maxv=100, desc="Близько 100% — нові поди не плануються (Resource Starvation)"), 12, 8)
b.add(ts("Limits CPU / allocatable вузла, %", PROM, [tgt(PROM, 'sum by (node) (kube_pod_container_resource_limits{resource="cpu"}) / sum by (node) (kube_node_status_allocatable{resource="cpu"}) * 100', "{{node}}")],
         unit="percent"), 12, 8)
BOARDS.append(b)

b = Board("lab9-talos-logs", "Talos — логи ОС і кластера (Vector → Loki)", ["lab9", "talos", "loki"],
          [qvar("node", "Вузол", LOKI, ('{job="talos"}', "node")),
           qvar("service", "Сервіс Talos", LOKI, ('{job="talos"}', "service")),
           cvar("level", "Рівень", ["error", "warn", "warning", "info", "debug"])], time_from="now-1h")
b.add(ts("Рядків логів за сервісом", LOKI, [tgt(LOKI, 'sum by (service) (count_over_time({job="talos", node=~"$node", service=~"$service"}[$__auto]))', "{{service}}")],
         stack=True, draw="bars"), 12, 8)
b.add(ts("Помилки та попередження за вузлом", LOKI, [tgt(LOKI, 'sum by (node, level) (count_over_time({job="talos", node=~"$node", level=~"error|warn|warning"}[$__auto]))', "{{node}} {{level}}")],
         draw="bars"), 12, 8)
b.add(logs("Сервіси Talos (machined, apid, kubelet, etcd, containerd...)",
           '{job="talos", stream="service", node=~"$node", service=~"$service", level=~"$level"}'), 24, 12)
b.add(logs("Ядро (kmsg)", '{job="talos", stream="kernel", node=~"$node"}'), 24, 10)
b.add(logs("Логи подів (Vector-агент)", '{job="kubernetes", node=~"$node"}'), 24, 10)
BOARDS.append(b)

b = Board("lab9-runtime-security", "Runtime Security — Falco і аудит K8s", ["lab9", "falco", "security", "loki"],
          [cvar("priority", "Пріоритет Falco", ["Emergency", "Alert", "Critical", "Error", "Warning", "Notice", "Informational", "Debug"])],
          time_from="now-6h")
b.row("Falco (falcosidekick → Loki)")
b.add(stat("Подій Falco за період", LOKI, 'sum(count_over_time({rule=~".+", priority=~"$priority"}[$__range])) or vector(0)'), 6, 5)
b.add(stat("Warning і вище", LOKI, 'sum(count_over_time({rule=~".+", priority=~"Warning|Error|Critical|Alert|Emergency"}[$__range])) or vector(0)',
           thresholds=RED_IF_ANY), 6, 5)
b.add(ts("Події за пріоритетом", LOKI, [tgt(LOKI, 'sum by (priority) (count_over_time({rule=~".+", priority=~"$priority"}[$__auto]))', "{{priority}}")],
         stack=True, draw="bars"), 12, 10)
b.add(bargauge("Топ правил Falco", LOKI, 'topk(10, sum by (rule) (count_over_time({rule=~".+", priority=~"$priority"}[$__range])))', "{{rule}}"), 12, 10)
b.add(logs("Події Falco", '{rule=~".+", priority=~"$priority"} | json | line_format "{{.priority}} | {{.rule}} | {{.output}}"'), 24, 12)
b.row("Аудит Kubernetes API (Talos -> Vector-агент -> Loki)")
b.add(ts("Змінюючі запити до API за дієсловом", LOKI, [tgt(LOKI, 'sum by (verb) (count_over_time({job="k8s-audit", verb=~"create|update|patch|delete|deletecollection"}[$__auto]))', "{{verb}}")],
         stack=True, draw="bars"), 12, 8)
b.add(ts("Відмови 401/403 в аудиті", LOKI, [tgt(LOKI, 'sum(count_over_time({job="k8s-audit"} | json | responseStatus_code=~"401|403" [$__auto]))', "відмови")],
         draw="bars"), 12, 8)
b.add(logs("Зміни RBAC, секретів і exec у поди",
           '{job="k8s-audit"} | json | (objectRef_resource=~"roles|rolebindings|clusterroles|clusterrolebindings|secrets" and verb=~"create|update|patch|delete") or objectRef_subresource="exec"'), 24, 12)
BOARDS.append(b)

b = Board("lab9-alerts-backup", "Алерти і резервні копії", ["lab9", "alerts", "velero"], time_from="now-24h")
b.row("Алерти")
b.add(table("Активні алерти зараз (Prometheus)", PROM, 'ALERTS{alertstate="firing"}',
            hide=["Time", "Value", "__name__", "alertstate", "cluster"]), 24, 7)
b.add(ts("Доставлені сповіщення (Alertmanager → webhook → Loki)", LOKI,
         [tgt(LOKI, 'sum by (alertname, status) (count_over_time({job="alertmanager"}[$__auto]))', "{{alertname}} {{status}}")],
         draw="bars", stack=True), 12, 8)
b.add(ts("Alertmanager: надіслано / помилки за інтеграцією", PROM, [
    tgt(PROM, 'sum by (integration) (increase(alertmanager_notifications_total[$__rate_interval]))', "надіслано {{integration}}", ref="A"),
    tgt(PROM, 'sum by (integration) (increase(alertmanager_notifications_failed_total[$__rate_interval]))', "помилки {{integration}}", ref="B")],
    draw="bars"), 12, 8)
b.add(logs("Журнал сповіщень", '{job="alertmanager"} | json | line_format "{{.status}} [{{.severity}}] {{.alertname}}: {{.summary}}"'), 24, 10)
b.row("Velero")
b.add(stat("Від останнього успішного бекапу", PROM, 'time() - max(velero_backup_last_successful_timestamp{schedule!=""})', unit="s",
           thresholds=[{"color": "green", "value": None}, {"color": "orange", "value": 90000}, {"color": "red", "value": 180000}]), 6, 5)
b.add(stat("Успішних бекапів", PROM, 'sum(velero_backup_success_total) or vector(0)'), 6, 5)
b.add(stat("Невдалих бекапів", PROM, 'sum(velero_backup_failure_total) + sum(velero_backup_partial_failure_total) or vector(0)', thresholds=RED_IF_ANY), 6, 5)
b.add(stat("Відновлень", PROM, 'sum(velero_restore_success_total) or vector(0)'), 6, 5)
b.add(ts("Тривалість бекапів (середня)", PROM, [tgt(PROM, 'sum by (schedule) (rate(velero_backup_duration_seconds_sum[1h])) / sum by (schedule) (rate(velero_backup_duration_seconds_count[1h]))', "{{schedule}}")],
         unit="s"), 24, 7)
BOARDS.append(b)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for board in BOARDS:
        path = OUT / f"{board.uid}.json"
        path.write_text(json.dumps(board.dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{path.name}: {len(board.panels)} панелей")


if __name__ == "__main__":
    main()

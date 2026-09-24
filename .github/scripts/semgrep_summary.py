"""Будує таблицю знахідок Semgrep у Job Summary і валить збірку на ERROR."""
import json
import os
import sys

BLOCKING = {"ERROR"}  # додайте "WARNING", щоб зробити гейт суворішим

path = sys.argv[1] if len(sys.argv) > 1 else "semgrep.json"
with open(path, encoding="utf-8") as f:
    results = json.load(f).get("results", [])

order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
results.sort(key=lambda r: (order.get(r["extra"]["severity"], 9), r["path"], r["start"]["line"]))

counts = {}
for r in results:
    sev = r["extra"]["severity"]
    counts[sev] = counts.get(sev, 0) + 1

lines = ["## Semgrep: результати SAST", ""]
lines.append(" | ".join(f"**{k}**: {v}" for k, v in sorted(counts.items(), key=lambda kv: order.get(kv[0], 9))) or "Знахідок немає ✅")
lines += ["", "| Severity | Файл:рядок | Правило | CWE |", "|---|---|---|---|"]
for r in results:
    cwe = r["extra"].get("metadata", {}).get("cwe", "")
    if isinstance(cwe, list):
        cwe = cwe[0] if cwe else ""
    rule = r["check_id"].split(".")[-1]
    lines.append(f"| {r['extra']['severity']} | `{r['path']}:{r['start']['line']}` | {rule} | {str(cwe).split(':')[0]} |")

report = "\n".join(lines)
summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
if summary_file:
    with open(summary_file, "a", encoding="utf-8") as f:
        f.write(report + "\n")
print(report)

blocking = sum(v for k, v in counts.items() if k in BLOCKING)
if blocking:
    print(f"\n❌ Quality gate: {blocking} знахідок рівня {', '.join(sorted(BLOCKING))}")
    sys.exit(1)
print("\n✅ Quality gate пройдено")

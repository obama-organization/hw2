import json
import os
import sys

BLOCKING = {"ERROR"}
ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}

path = sys.argv[1] if len(sys.argv) > 1 else "semgrep.json"
with open(path, encoding="utf-8") as f:
    results = json.load(f).get("results", [])

results.sort(key=lambda r: (ORDER.get(r["extra"]["severity"], 9), r["path"], r["start"]["line"]))

counts = {}
for r in results:
    severity = r["extra"]["severity"]
    counts[severity] = counts.get(severity, 0) + 1

totals = " | ".join(
    f"**{k}**: {v}" for k, v in sorted(counts.items(), key=lambda kv: ORDER.get(kv[0], 9))
)
lines = ["## Semgrep SAST results", "", totals or "No findings", ""]
lines += ["| Severity | File:line | Rule | CWE |", "|---|---|---|---|"]
for r in results:
    cwe = r["extra"].get("metadata", {}).get("cwe", "")
    if isinstance(cwe, list):
        cwe = cwe[0] if cwe else ""
    rule = r["check_id"].split(".")[-1]
    location = f"{r['path']}:{r['start']['line']}"
    lines.append(f"| {r['extra']['severity']} | `{location}` | {rule} | {str(cwe).split(':')[0]} |")

report = "\n".join(lines)
summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
if summary_file:
    with open(summary_file, "a", encoding="utf-8") as f:
        f.write(report + "\n")
print(report)

blocking = sum(v for k, v in counts.items() if k in BLOCKING)
if blocking:
    print(f"\nQuality gate failed: {blocking} finding(s) with severity {', '.join(sorted(BLOCKING))}")
    sys.exit(1)
print("\nQuality gate passed")

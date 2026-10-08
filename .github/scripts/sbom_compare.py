import json
import os
import sys

BLOCKING = {"CRITICAL"}
SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NEGLIGIBLE", "UNKNOWN"]

sbom_path, trivy_path, grype_path = sys.argv[1:4]


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def key(name, version):
    return f"{name.lower().replace('_', '-')}@{version}"


def ecosystem(purl):
    return purl.split(":", 1)[1].split("/", 1)[0] if purl.startswith("pkg:") else "other"


def grype_id(match):
    vuln_id = match["vulnerability"]["id"]
    if vuln_id.startswith("CVE-"):
        return vuln_id
    related = [r["id"] for r in match.get("relatedVulnerabilities") or [] if r["id"].startswith("CVE-")]
    return related[0] if related else vuln_id


sbom = load(sbom_path)
trivy = load(trivy_path)
grype = load(grype_path)

components = {
    key(c["name"], c.get("version", "")): ecosystem(c.get("purl", ""))
    for c in sbom.get("components", [])
    if c.get("type") != "file"
}

trivy_packages = set()
trivy_vulns = {}
for result in trivy.get("Results") or []:
    for package in result.get("Packages") or []:
        trivy_packages.add(key(package["Name"], package.get("Version", "")))
    for vuln in result.get("Vulnerabilities") or []:
        finding = (vuln["VulnerabilityID"], key(vuln["PkgName"], vuln["InstalledVersion"]))
        trivy_vulns[finding] = vuln["Severity"].upper()

grype_vulns = {}
for match in grype.get("matches") or []:
    artifact = match["artifact"]
    finding = (grype_id(match), key(artifact["name"], artifact["version"]))
    grype_vulns[finding] = match["vulnerability"]["severity"].upper()

lines = ["## SBOM check: Syft, Trivy and Grype", ""]
lines += ["| Ecosystem | Components in SBOM | Identified by Trivy |", "|---|---|---|"]
for eco in sorted(set(components.values())):
    names = [name for name, value in components.items() if value == eco]
    identified = [name for name in names if name in trivy_packages]
    lines.append(f"| {eco} | {len(names)} | {len(identified)} |")
lines.append(f"| **total** | **{len(components)}** | **{len(trivy_packages & set(components))}** |")

missing = sorted(set(components) - trivy_packages)
if missing:
    lines += ["", "Components that Trivy does not identify: " + ", ".join(f"`{m}`" for m in missing)]

lines += ["", "| Severity | Trivy | Grype |", "|---|---|---|"]
for severity in SEVERITIES:
    trivy_count = sum(1 for value in trivy_vulns.values() if value == severity)
    grype_count = sum(1 for value in grype_vulns.values() if value == severity)
    lines.append(f"| {severity} | {trivy_count} | {grype_count} |")
lines.append(f"| **total** | **{len(trivy_vulns)}** | **{len(grype_vulns)}** |")

only_trivy = sorted(set(trivy_vulns) - set(grype_vulns))
only_grype = sorted(set(grype_vulns) - set(trivy_vulns))
if only_trivy:
    lines += ["", "Found only by Trivy: " + ", ".join(f"`{v} ({p})`" for v, p in only_trivy)]
if only_grype:
    lines += ["", "Found only by Grype: " + ", ".join(f"`{v} ({p})`" for v, p in only_grype)]
if not only_trivy and not only_grype:
    lines += ["", "Trivy and Grype report the same set of vulnerabilities."]

report = "\n".join(lines)
summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
if summary_file:
    with open(summary_file, "a", encoding="utf-8") as f:
        f.write(report + "\n")
print(report)

blocking = sum(1 for value in list(trivy_vulns.values()) + list(grype_vulns.values()) if value in BLOCKING)
if blocking:
    print(f"\nQuality gate failed: {blocking} finding(s) with severity {', '.join(sorted(BLOCKING))}")
    sys.exit(1)
print("\nQuality gate passed")

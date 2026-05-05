import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from bson import ObjectId
from pathlib import Path

from local.api_app.models.sbom_models import SbomModel


# -----------------------------
# SBOM GENERATION (OPTIONAL)
# -----------------------------
def _run_syft(project_path: str, sbom_path: Path):
    result = subprocess.run(
        ["syft", f"dir:{project_path}", "-o", f"cyclonedx-json={sbom_path}"],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    if result.returncode != 0:
        raise Exception(f"Syft failed: {result.stderr}")

    if not sbom_path.exists():
        raise Exception("Syft did not produce SBOM file")


# -----------------------------
# GRYPE SCAN (stdout based)
# -----------------------------
def _run_grype(sbom_path: Path):
    result = subprocess.run(
        ["grype", f"sbom:{sbom_path}", "-o", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    if result.returncode != 0:
        raise Exception(f"Grype failed: {result.stderr}")

    return json.loads(result.stdout)


# -----------------------------
# GRANT SCAN (stdout based)
# -----------------------------
def _run_grant(sbom_path: Path):
    result = subprocess.run(
        ["grant", "list", str(sbom_path), "--output", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    if result.returncode != 0:
        raise Exception(f"Grant failed: {result.stderr}")

    return json.loads(result.stdout)


# -----------------------------
# SBOM FORMAT DETECTION
# -----------------------------
def _detect_sbom_format(sbom_path: str) -> str:
    with open(sbom_path, encoding="utf-8") as f:
        data = json.load(f)

    if "artifacts" in data:
        return "syft-json"
    if "bomFormat" in data:
        return "cyclonedx-json"
    if "spdxVersion" in data:
        return "spdx-json"

    return "unknown"


# -----------------------------
# RISK NORMALIZATION
# -----------------------------
def _normalize_risk(risk: str):
    risk = (risk or "").lower()

    if "low" in risk:
        return "low"
    if "medium" in risk:
        return "medium"
    if "high" in risk:
        return "high"

    return "unknown"


# -----------------------------
# SBOM NORMALIZATION (FALLBACK)
# -----------------------------
def _convert_to_syft(input_path: str, output_path: str):
    subprocess.run(
        ["syft", "convert", input_path, "-o", f"json={str(output_path)}"],
        check=True
    )


# -----------------------------
# SBOM HELPERS
# -----------------------------
def _extract_purl_from_spdx(pkg: dict):
    for ref in pkg.get("externalRefs", []):
        if ref.get("referenceType") == "purl":
            return ref.get("referenceLocator")
    return None


def _extract_type_from_purl(purl: str):
    if not purl:
        return None
    try:
        return purl.split("/")[0].split(":")[1]
    except Exception:
        return None


def _iter_dependencies(sbom: dict):
    if "artifacts" in sbom:
        for a in sbom["artifacts"]:
            yield {"name": a.get("name"), "type": a.get("type")}

    elif "components" in sbom:
        for c in sbom["components"]:
            yield {"name": c.get("name"), "type": c.get("type")}

    elif "packages" in sbom:
        for p in sbom["packages"]:
            purl = _extract_purl_from_spdx(p)
            yield {
                "name": p.get("name"),
                "version": p.get("versionInfo"),
                "type": _extract_type_from_purl(purl),
            }


def _extract_ecosystems(sbom: dict):
    return list({d["type"].lower() for d in _iter_dependencies(sbom) if d.get("type")})


def _count_dependencies(sbom: dict):
    return sum(1 for _ in _iter_dependencies(sbom))


# -----------------------------
# PARSERS
# -----------------------------
def _parse_grype_results(grype_output: dict, scan_id: str):
    findings = []
    severity_counts = defaultdict(int)

    for match in grype_output.get("matches", []):
        vuln = match.get("vulnerability", {})
        artifact = match.get("artifact", {})

        severity = vuln.get("severity", "unknown").lower()
        severity_counts[severity] += 1

        findings.append({
            "scan_id": ObjectId(scan_id),
            "package_name": artifact.get("name"),
            "package_version": artifact.get("version"),
            "package_type": artifact.get("type"),
            "cve_id": vuln.get("id"),
            "severity": severity,
            "description": vuln.get("description"),
            "cvss": vuln.get("cvss", []),
            "fix_versions": vuln.get("fix", {}).get("versions", []),
            "created_at": datetime.now(timezone.utc),
        })

    return findings, severity_counts


def _parse_grant_results(grant_output: dict, scan_id: str):
    findings = []
    risk_counts = defaultdict(int)

    for pkg in grant_output.get("findings", {}).get("packages", []):
        for lic in pkg.get("licenses", []):
            risk_category = lic.get("riskCategory", "unknown")
            risk_level = _normalize_risk(risk_category)

            risk_counts[risk_level] += 1

            findings.append({
                "scan_id": ObjectId(scan_id),
                "package_name": pkg.get("name"),
                "package_version": pkg.get("version"),
                "package_type": pkg.get("type"),
                "license": {
                    "id": lic.get("id"),
                    "reference": lic.get("reference"),
                    "osi_approved": lic.get("isOsiApproved"),
                    "risk_category": risk_category,
                    "risk_level": risk_level,
                },
                "decision": pkg.get("decision"),
                "locations": pkg.get("locations", []),
                "created_at": datetime.now(timezone.utc),
            })

    return findings, risk_counts

def _parse_grant_check_results(grant_output: dict, scan_id: str):
    findings = []
    risk_counts = defaultdict(int)

    targets = grant_output.get("run", {}).get("targets", [])

    for target in targets:
        evaluation = target.get("evaluation", {})
        packages = evaluation.get("findings", {}).get("packages", [])

        for pkg in packages:

            licenses = pkg.get("licenses", [])

            # ⚠️ Important edge case:
            # packages with NO licenses (your example shows this)
            if not licenses:
                findings.append({
                    "scan_id": ObjectId(scan_id),
                    "package_name": pkg.get("name"),
                    "package_version": pkg.get("version"),
                    "package_type": pkg.get("type"),

                    "license": {
                        "id": None,
                        "reference": None,
                        "osi_approved": None,
                        "risk_category": "unlicensed",
                        "risk_level": "high",  # you can decide policy here
                    },

                    "decision": pkg.get("decision"),
                    "locations": pkg.get("locations", []),

                    "created_at": datetime.now(timezone.utc),
                })

                risk_counts["high"] += 1
                continue

            # Normal licensed packages
            for lic in licenses:
                risk_category = lic.get("riskCategory", "unknown")
                risk_level = _normalize_risk(risk_category)

                risk_counts[risk_level] += 1

                findings.append({
                    "scan_id": ObjectId(scan_id),

                    "package_name": pkg.get("name"),
                    "package_version": pkg.get("version"),
                    "package_type": pkg.get("type"),

                    "license": {
                        "id": lic.get("id"),
                        "reference": lic.get("reference"),
                        "osi_approved": lic.get("isOsiApproved"),
                        "risk_category": risk_category,
                        "risk_level": risk_level,
                    },

                    "decision": pkg.get("decision"),
                    "locations": pkg.get("locations", []),

                    "created_at": datetime.now(timezone.utc),
                })

    return findings, risk_counts
# -----------------------------
# MAIN PIPELINE
# -----------------------------
def run_sbom_pipeline(sbom_path: str, scan_id: str, triggered_by=None):

    vuln_db = SbomModel.findings_collection
    license_db = SbomModel.licenses_findings_collection

    output_dir = Path("output") / str(scan_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    normalized_sbom_path = output_dir / "normalized-sbom.json"

    # Detect + normalize
    sbom_format = _detect_sbom_format(sbom_path)

    if sbom_format in ["syft-json", "cyclonedx-json", "spdx-json"]:
        normalized_sbom_path = Path(sbom_path)
    else:
        _convert_to_syft(sbom_path, normalized_sbom_path)

    with open(normalized_sbom_path, encoding="utf-8") as f:
        sbom = json.load(f)

    dependencies_count = _count_dependencies(sbom)
    ecosystems = _extract_ecosystems(sbom)

    # -------- GRYPE --------
    try:
        grype_output = _run_grype(normalized_sbom_path)
        findings, severity_counts = _parse_grype_results(grype_output, scan_id)

        if findings:
            vuln_db.insert_many(findings)

    except Exception as e:
        severity_counts = defaultdict(int)
        findings = []
        print(f"Grype failed: {e}")

    # -------- GRANT --------
    try:
        grant_output = _run_grant(normalized_sbom_path)
        if "run" in grant_output:
            license_findings, risk_counts = _parse_grant_check_results(grant_output=grant_output, scan_id=scan_id)
        else:
            license_findings, risk_counts = _parse_grant_results(grant_output=grant_output, scan_id=scan_id)

        if license_findings:
            license_db.insert_many(license_findings)

        SbomModel.scans_collection.update_one(
            {"_id": ObjectId(scan_id)},
            {
                "$set": {
                    "license_policy": grant_output.get("run", {}).get("policy", {}),
                    # "license_summary": evaluation.get("summary", {})
                }
            }
        )

    except Exception as e:
        risk_counts = defaultdict(int)
        license_findings = []
        print(f"Grant failed: {e}")

    return {
        "dependencies_scanned": dependencies_count,
        "total_vulnerabilities": len(findings),
        "total_licenses": len(license_findings),

        "severity_counts": {
            "critical": severity_counts.get("critical", 0),
            "high": severity_counts.get("high", 0),
            "medium": severity_counts.get("medium", 0),
            "low": severity_counts.get("low", 0),
            "negligible": severity_counts.get("negligible", 0),
        },

        "license_risk_counts": {
            "low": risk_counts.get("low", 0),
            "medium": risk_counts.get("medium", 0),
            "high": risk_counts.get("high", 0),
        },

        "ecosystems": ecosystems,
    }
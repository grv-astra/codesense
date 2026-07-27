from collections import defaultdict
from datetime import datetime, timedelta, timezone

from django.db.models import Count
from local.auth_app.permissions.decorators import require_authentication
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from local.api_app.models.orm import (
    Project, Scan, Finding, SbomScan, SbomFinding,
)


def _severity_defaults() -> dict:
    return {"critical": 0, "high": 0, "medium": 0, "low": 0}


_TREND_WINDOWS = {
    "users": (timedelta(days=7), "than last week"),
    "projects": (timedelta(days=30), "than last month"),
    "scans": (timedelta(days=1), "than yesterday"),
    "sbom_scans": (timedelta(days=7), "than last week"),
}


def _pct_change(current: int, previous: int) -> float:
    if previous:
        return round((current - previous) / previous * 100, 1)
    return 100.0 if current else 0.0


class DashboardView(APIView):
    @require_authentication()
    def get(self, request):
        try:
            response_data = {
                "top_counts": {
                    "users": _user_count(),
                    "projects": Project.objects.filter(deleted=False).count(),
                    "scans": Scan.objects.filter(deleted=False).count(),
                    "findings": Finding.objects.filter(deleted=False).count(),
                    "sbom_scans": SbomScan.objects.filter(deleted=False).count(),
                    # NB: SbomFinding has no `deleted` field (no soft-delete), so count all rows.
                    "sbom_findings": SbomFinding.objects.count(),
                },
                "top_counts_trend": self._get_top_counts_trend(),
                "system_status": self._get_system_status(),
                "count_by_severity": self._get_severity_counts(),
                "language_distribution": self._get_language_distribution(),
                "findings_trend": self._get_findings_trend(self._parse_trend_days(request)),
                "top_cwe": self._get_top_cwe(),
                "scans_by_project": self._get_scans_by_project(),
                "scan_distribution": self._get_scan_distribution(),
                "recent_scans": self._get_recent_scans(),
            }
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def _get_top_counts_trend(self):
        from local.auth_app.models.orm import User

        now = datetime.now(timezone.utc)
        querysets = {
            "users": User.objects.filter(deleted=False),
            "projects": Project.objects.filter(deleted=False),
            "scans": Scan.objects.filter(deleted=False),
            "sbom_scans": SbomScan.objects.filter(deleted=False),
        }
        trend = {}
        for key, (window, period) in _TREND_WINDOWS.items():
            qs = querysets[key]
            current = qs.count()
            previous = qs.filter(created_at__lte=now - window).count()
            trend[key] = {"pct": _pct_change(current, previous), "period": period}
        return trend

    def _get_system_status(self):
        rows = (Scan.objects.filter(deleted=False).values("status")
                .annotate(count=Count("id")))
        counts = {r["status"]: r["count"] for r in rows}
        return {"counts": counts, "total_scans": sum(counts.values())}

    def _get_severity_counts(self):
        counts = _severity_defaults()
        rows = (Finding.objects.filter(deleted=False).values("severity")
                .annotate(count=Count("id")))
        for r in rows:
            sev = str(r["severity"] or "").lower()
            if sev in counts:
                counts[sev] = r["count"]
        return counts

    def _get_language_distribution(self):
        acc = {}
        for scan in Scan.objects.filter(deleted=False).only("metrics", "findings"):
            langs = (scan.metrics or {}).get("languages") or []
            for lang in langs:
                bucket = acc.setdefault(lang, {"language": lang, "vulnerabilities": 0, "scans": 0})
                bucket["vulnerabilities"] += scan.findings or 0
                bucket["scans"] += 1
        rows = sorted(acc.values(),
                      key=lambda r: (-r["vulnerabilities"], -r["scans"], r["language"]))
        return rows[:8]

    TREND_DAY_OPTIONS = (7, 30, 90)

    def _parse_trend_days(self, request):
        try:
            days = int(request.query_params.get("trend_days", 7))
        except (TypeError, ValueError):
            days = 7
        return days if days in self.TREND_DAY_OPTIONS else 7

    def _get_findings_trend(self, days=7):
        start_date = datetime.now(timezone.utc) - timedelta(days=days - 1)
        grouped = {}
        for f in Finding.objects.filter(deleted=False, created_at__gte=start_date).only(
            "created_at", "severity"
        ):
            date_key = f.created_at.strftime("%Y-%m-%d")
            sev = str(f.severity or "").lower()
            day_bucket = grouped.setdefault(
                date_key, {"critical": 0, "high": 0, "medium": 0, "low": 0}
            )
            if sev in day_bucket:
                day_bucket[sev] += 1

        trend = []
        for offset in range(days):
            day = (start_date + timedelta(days=offset)).date()
            key = day.strftime("%Y-%m-%d")
            values = grouped.get(key, {"critical": 0, "high": 0, "medium": 0, "low": 0})
            total = values["critical"] + values["high"] + values["medium"] + values["low"]
            trend.append({"date": day.strftime("%b %d"), **values, "total": total})
        return trend

    def _get_top_cwe(self):
        rows = (Finding.objects.filter(deleted=False)
                .exclude(cwe__in=["", None])
                .values("cwe").annotate(count=Count("id"))
                .order_by("-count", "cwe")[:10])
        results = []
        for r in rows:
            cwe_value = str(r["cwe"] or "")
            parts = cwe_value.split(":", 1)
            cwe_id = parts[0].strip()
            name = parts[1].strip() if len(parts) > 1 else cwe_id
            results.append({"id": cwe_id, "name": name, "count": r["count"]})
        return results

    def _get_scans_by_project(self):
        scans = list(Scan.objects.filter(deleted=False).only(
            "project_id", "findings"
        ))
        if not scans:
            return []
        project_ids = {s.project_id for s in scans}
        names = {str(p.id): p.name for p in Project.objects.filter(id__in=project_ids)}

        # critical findings per project (join findings -> scans by scan_id)
        scan_to_project = {str(s.id): s.project_id for s in
                           Scan.objects.filter(deleted=False).only("project_id")}
        crit_by_project = defaultdict(int)
        for f in Finding.objects.filter(deleted=False, severity="critical").only("scan_id"):
            pid = scan_to_project.get(str(f.scan_id))
            if pid is not None:
                crit_by_project[pid] += 1

        agg = {}
        for s in scans:
            row = agg.setdefault(s.project_id, {"_id": s.project_id, "scans": 0, "findings": 0})
            row["scans"] += 1
            row["findings"] += s.findings or 0

        rows = []
        for pid, row in agg.items():
            rows.append({
                "project": names.get(str(pid), "Unknown Project"),
                "scans": row["scans"],
                "findings": row["findings"],
                "critical": crit_by_project.get(pid, 0),
            })
        rows.sort(key=lambda r: (-r["findings"], -r["scans"], r["project"]))
        return rows[:10]

    def _get_recent_scans(self, limit=8):
        projects = {str(p.id): p.name for p in Project.objects.filter(deleted=False)}

        code_rows = (Scan.objects.filter(deleted=False)
                     .only("id", "project_id", "scan_name", "status", "created_at", "findings")
                     .order_by("-created_at")[:limit])
        sbom_rows = (SbomScan.objects.filter(deleted=False)
                     .only("id", "project_id", "scan_name", "status", "created_at", "vulnerabilities")
                     .order_by("-created_at")[:limit])

        combined = []
        for s in code_rows:
            combined.append({
                "id": str(s.id),
                "type": "code",
                "project": projects.get(str(s.project_id), "Unknown Project"),
                "scan_name": s.scan_name or "Code Scan",
                "status": s.status,
                "findings": s.findings or 0,
                "created_at": s.created_at.isoformat(),
            })
        for s in sbom_rows:
            combined.append({
                "id": str(s.id),
                "type": "sbom",
                "project": projects.get(str(s.project_id), "Unknown Project"),
                "scan_name": s.scan_name or "SBOM Scan",
                "status": s.status,
                "findings": s.vulnerabilities or 0,
                "created_at": s.created_at.isoformat(),
            })

        combined.sort(key=lambda r: r["created_at"], reverse=True)
        return combined[:limit]

    def _get_scan_distribution(self):
        """Code (SAST) scans vs SBOM (SCA) scans."""
        return [
            {
                "name": "Code Scans",
                "value": Scan.objects.filter(deleted=False).count(),
                "color": "#8b5cf6",
            },
            {
                "name": "SBOM Scans",
                "value": SbomScan.objects.filter(deleted=False).count(),
                "color": "#ec4899",
            },
        ]


def _user_count():
    from local.auth_app.models.orm import User
    return User.objects.filter(deleted=False).count()

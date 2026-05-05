import { DotsLoader } from '@/components/atomic/loader';
import { useSbomScanDetails } from '@/hooks/use-scans';
import { createFileRoute, useNavigate, useParams } from '@tanstack/react-router'
import { Shield, AlertTriangle, Package, CheckCircle, XCircle, Activity, Clock, Layers } from 'lucide-react';

export const Route = createFileRoute(
  '/_authenticated/scan/sbom/$sbomscanId/updates',
)({
  component: SecurityDashboard,
})

function SecurityDashboard() {
  const navigate = useNavigate();

  // const scanData = {
  //   id: "69dc8f8f1db71b54c64b9f43",
  //   project_id: "69d4e7282279562ec04b684e",
  //   scan_name: "sbom_test",
  //   status: "completed",
  //   created_at: "2026-04-13T06:39:11.219000",
  //   triggered_by: "69d4e6bd0f4f9811c2016fc5",
  //   dependencies_scanned: 168,
  //   vulnerabilities: 27,
  //   severity_counts: {
  //     critical: 1,
  //     high: 13,
  //     medium: 5,
  //     low: 8,
  //     negligible: 0
  //   },
  //   ecosystems: ["library"],
  //   sbom_format: "syft-json",
  //   end_time: "2026-04-13T06:40:02.773000"
  // };

  const { sbomscanId } = useParams({ from: '/_authenticated/scan/sbom/$sbomscanId/updates' });
  const { data, isLoading } = useSbomScanDetails(sbomscanId)

  const scanData = data

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if(isLoading) return <DotsLoader />

  const getScanDurationSeconds = () => {
    const start = new Date(scanData.created_at).getTime();
    const end = new Date(scanData.end_time).getTime();
    return Math.round((end - start) / 1000);
  };

  const affectedPercentage = ((scanData.vulnerabilities / scanData.dependencies_scanned) * 100).toFixed(1);
  const cleanDependencies = scanData.dependencies_scanned - scanData.vulnerabilities;

  const totalSeverity = Object.values(scanData.severity_counts).reduce((a, b) => a + b, 0);

  const severityConfig: Record<string, { bg: string; text: string; label: string }> = {
    critical: { bg: 'bg-primary', text: 'text-primary', label: 'Critical' },
    high:     { bg: 'bg-chart-5', text: 'text-chart-5', label: 'High' },
    medium:   { bg: 'bg-chart-4', text: 'text-chart-4', label: 'Medium' },
    low:      { bg: 'bg-chart-2', text: 'text-chart-2', label: 'Low' },
    negligible: { bg: 'bg-muted-foreground', text: 'text-muted-foreground', label: 'Negligible' },
  };

  // Derive overall risk level from severity counts
  const getRiskLevel = () => {
    if (scanData.severity_counts.critical > 0) return 'HIGH';
    if (scanData.severity_counts.high > 5) return 'MEDIUM';
    if (scanData.severity_counts.high > 0) return 'MEDIUM';
    return 'LOW';
  };

  const riskLevel = getRiskLevel();

  return (
    <div className="">
      <div className="min-h-screen bg-background transition-colors duration-300 rounded-lg">
        <div className="px-8 py-8 space-y-6">

          {/* Status Banner */}
          <div className="bg-card rounded-xl border border-border overflow-hidden">
            <div className="flex items-stretch">
              <div className="bg-primary px-8 py-6 flex items-center justify-center min-w-[200px]">
                <div className="text-center">
                  <div className="text-primary-foreground text-sm font-semibold uppercase tracking-wider mb-2">Overall Risk</div>
                  <div className="text-5xl font-bold text-primary-foreground mb-1">{riskLevel}</div>
                  <div className="text-primary-foreground/80 text-sm capitalize">{scanData.status}</div>
                </div>
              </div>
              <div className="flex-1 px-8 py-6 grid grid-cols-4 gap-6">
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">Started</div>
                    <div className="text-sm font-medium text-foreground mt-1">{formatTimestamp(scanData.created_at)}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">Duration</div>
                    <div className="text-sm font-medium text-foreground mt-1">{getScanDurationSeconds()}s</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Activity className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">Scan Name</div>
                    <div className="text-sm font-medium text-foreground mt-1">{scanData.scan_name}</div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Layers className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <div className="text-xs text-muted-foreground uppercase tracking-wide">Format</div>
                    <div className="text-sm font-medium text-foreground mt-1">{scanData.sbom_format}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Key Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div
              className="bg-card rounded-xl border border-border p-6 hover:border-primary transition-colors cursor-pointer"
              onClick={() => navigate({ to: '/scan/sbom/$sbomscanId/dependencies', params: { sbomscanId: scanData.id } })}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                  <Package className="w-6 h-6 text-foreground" />
                </div>
                <div className="text-3xl font-bold text-foreground">{scanData.dependencies_scanned}</div>
              </div>
              <h3 className="text-foreground font-semibold text-lg">Total Dependencies</h3>
              <p className="text-muted-foreground text-sm mt-1">Packages scanned in project</p>
            </div>

            <div className="bg-card rounded-xl border border-border p-6 hover:border-primary transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                  <AlertTriangle className="w-6 h-6 text-primary" />
                </div>
                <div className="text-3xl font-bold text-primary">{scanData.vulnerabilities}</div>
              </div>
              <h3 className="text-foreground font-semibold text-lg">Vulnerabilities</h3>
              <p className="text-muted-foreground text-sm mt-1">{affectedPercentage}% of dependencies affected</p>
            </div>

            <div className="bg-card rounded-xl border border-border p-6 hover:border-primary transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                  <XCircle className="w-6 h-6 text-foreground" />
                </div>
                <div className="text-3xl font-bold text-foreground">{scanData.severity_counts.critical + scanData.severity_counts.high}</div>
              </div>
              <h3 className="text-foreground font-semibold text-lg">Critical & High</h3>
              <p className="text-muted-foreground text-sm mt-1">Require immediate attention</p>
            </div>

            <div className="bg-card rounded-xl border border-border p-6 hover:border-primary transition-colors">
              <div className="flex items-start justify-between mb-4">
                <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                  <CheckCircle className="w-6 h-6 text-foreground" />
                </div>
                <div className="text-3xl font-bold text-foreground">{cleanDependencies}</div>
              </div>
              <h3 className="text-foreground font-semibold text-lg">Clean Packages</h3>
              <p className="text-muted-foreground text-sm mt-1">No issues found</p>
            </div>
          </div>

          {/* Analysis Sections */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Severity Distribution */}
            <div className="bg-card rounded-xl border border-border p-6">
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-foreground">Severity Distribution</h2>
                <p className="text-sm text-muted-foreground mt-1">Breakdown of vulnerabilities by risk level</p>
              </div>
              <div className="space-y-4">
                {Object.entries(scanData.severity_counts).map(([severity, count]) => {
                  const percentage = totalSeverity > 0 ? (count / totalSeverity) * 100 : 0;
                  const config = severityConfig[severity];
                  return (
                    <div key={severity} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className={`w-3 h-3 rounded ${config.bg}`} />
                          <span className="text-sm font-medium text-foreground">{config.label}</span>
                        </div>
                        <span className={`text-sm font-bold ${config.text}`}>{count}</span>
                      </div>
                      <div className="relative w-full bg-muted rounded-full h-2 overflow-hidden">
                        <div
                          className={`absolute h-full ${config.bg} transition-all duration-700 ease-out rounded-full`}
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Scan Metadata */}
            <div className="bg-card rounded-xl border border-border p-6">
              <div className="mb-6">
                <h2 className="text-xl font-semibold text-foreground">Scan Details</h2>
                <p className="text-sm text-muted-foreground mt-1">Metadata and configuration for this scan</p>
              </div>
              <div className="space-y-4">
                {[
                  { label: 'Scan ID', value: scanData.id },
                  { label: 'Project ID', value: scanData.project_id },
                  { label: 'SBOM Format', value: scanData.sbom_format },
                  { label: 'Ecosystems', value: scanData.ecosystems.join(', ') },
                  { label: 'Completed', value: formatTimestamp(scanData.end_time) },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                    <span className="text-sm text-muted-foreground">{label}</span>
                    <span className="text-sm font-medium text-foreground truncate ml-4 max-w-[220px] text-right">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Severity Breakdown Cards */}
          <div className="bg-card rounded-xl border border-border p-6">
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-foreground">Vulnerability Breakdown</h2>
              <p className="text-sm text-muted-foreground mt-1">Count by severity level</p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {Object.entries(scanData.severity_counts).map(([severity, count]) => {
                const config = severityConfig[severity];
                const isCritical = severity === 'critical';
                const isHigh = severity === 'high';
                return (
                  <div
                    key={severity}
                    className={`p-5 rounded-xl border-2 transition-colors ${
                      isCritical
                        ? 'bg-gradient-to-br from-primary/10 to-primary/5 border-primary/30 hover:border-primary'
                        : isHigh
                        ? 'bg-gradient-to-br from-chart-5/10 to-chart-5/5 border-chart-5/30 hover:border-chart-5'
                        : 'bg-muted border-border hover:border-primary'
                    }`}
                  >
                    <div className="text-4xl font-bold text-foreground mb-2">{count}</div>
                    <div className={`text-xs font-semibold uppercase tracking-wider ${config.text}`}>
                      {config.label}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Summary Footer */}
          <div className="bg-card rounded-xl p-8 border border-border">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-background rounded-lg flex items-center justify-center flex-shrink-0">
                <Shield className="w-6 h-6 text-foreground" />
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold mb-2">Executive Summary</h3>
                <p className="text-foreground/90 leading-relaxed">
                  Scan <span className="font-semibold">{scanData.scan_name}</span> completed in {getScanDurationSeconds()} seconds, analysing {scanData.dependencies_scanned} dependencies across {scanData.ecosystems.join(', ')} ecosystems using the {scanData.sbom_format} format.{' '}
                  {scanData.vulnerabilities} vulnerabilities were detected, including{' '}
                  <span className="font-semibold">{scanData.severity_counts.critical} critical</span> and{' '}
                  <span className="font-semibold">{scanData.severity_counts.high} high</span>-severity issues requiring immediate attention.{' '}
                  {cleanDependencies} packages ({(100 - parseFloat(affectedPercentage)).toFixed(1)}%) were found to be clean.
                </p>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
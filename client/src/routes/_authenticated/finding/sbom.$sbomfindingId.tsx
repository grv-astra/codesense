import { Button } from '@/components/atomic/button';
import { DotsLoader } from '@/components/atomic/loader';
import { useFindingDetails } from '@/hooks/use-finding';
import { createFileRoute, useParams, useRouter } from '@tanstack/react-router';
import { AlertTriangle, Package, Shield, CheckCircle2, Info, Activity, Target } from 'lucide-react';

export const Route = createFileRoute(
  '/_authenticated/finding/sbom/$sbomfindingId',
)({
  component: RouteComponent,
});

function RouteComponent() {
  const { sbomfindingId } = useParams({
    from: '/_authenticated/finding/sbom/$sbomfindingId',
  });
  const router = useRouter();
  const { data, isLoading } = useFindingDetails(sbomfindingId);

  if (isLoading) return <DotsLoader />;

  // Static data for demonstration
  const finding = {
    category: "DEPENDENCY_CONTEXT_RISK",
    package: "django",
    version: "4.2.7",
    severity: "MEDIUM",
    confidence: 0.81,
    title: "Common production misconfiguration risks in Django-based services",
    impact: "Misconfigured Django deployments may expose sensitive debug information or weaken request handling security.",
    evidence: [
      "Frequent production deployments with DEBUG enabled",
      "Improper middleware ordering patterns observed in real-world incidents"
    ],
    recommendation: [
      "Ensure DEBUG is disabled in production",
      "Review security middleware ordering",
      "Harden session and CSRF settings"
    ],
    owasp_mapping: ["A05"]
  };

  const getSeverityColor = (severity) => {
    const colors = {
      CRITICAL: 'bg-destructive/10 text-destructive border-destructive/30',
      HIGH: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/30',
      MEDIUM: 'bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-500/30',
      LOW: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30',
      INFO: 'bg-muted text-muted-foreground border-border',
    };
    return colors[severity] || colors.INFO;
  };

  const getSeverityIcon = (severity) => {
    const sizes = {
      CRITICAL: 'w-5 h-5',
      HIGH: 'w-5 h-5',
      MEDIUM: 'w-4 h-4',
      LOW: 'w-4 h-4',
      INFO: 'w-4 h-4',
    };
    return sizes[severity] || sizes.INFO;
  };

  const getConfidenceLevel = (confidence) => {
    if (confidence >= 0.8) return { label: 'High', color: 'text-green-600 dark:text-green-400', bg: 'bg-green-500/10' };
    if (confidence >= 0.6) return { label: 'Medium', color: 'text-yellow-600 dark:text-yellow-400', bg: 'bg-yellow-500/10' };
    return { label: 'Low', color: 'text-destructive', bg: 'bg-destructive/10' };
  };

  const confidenceInfo = getConfidenceLevel(finding.confidence);

  return (
    <div className="min-h-screen bg-background p-4 md:p-8">
      <Button variant="ghost" type="button" onClick={() => router.history.back()}>
        ←  Back to Findings
      </Button>
      <div className="space-y-6">
        {/* Hero Header with Gradient */}
        <div className="relative overflow-hidden bg-card rounded-xl border border-border shadow-lg">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-accent/5" />
          <div className="relative p-6 md:p-8">
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <AlertTriangle className="w-6 h-6 text-primary" />
                  </div>
                  <h1 className="text-2xl md:text-3xl font-semibold text-foreground leading-tight">
                    {finding.title}
                  </h1>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Activity className="w-4 h-4" />
                  <span className="font-medium">{finding.category.replace(/_/g, ' ')}</span>
                </div>
              </div>
              <div className="flex gap-2 flex-wrap">
                <span
                  className={`px-4 py-2 rounded-lg text-sm font-semibold border backdrop-blur-sm ${getSeverityColor(
                    finding.severity
                  )}`}
                >
                  <span className="flex items-center gap-2">
                    <Shield className={getSeverityIcon(finding.severity)} />
                    {finding.severity}
                  </span>
                </span>
              </div>
            </div>

            {/* Package Info Card */}
            <div className="bg-background/50 backdrop-blur-sm rounded-lg border border-border p-4">
              <div className="flex flex-wrap items-center gap-4 md:gap-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-md">
                    <Package className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Package</div>
                    <div className="font-semibold text-foreground">
                      {finding.package}
                      <span className="text-muted-foreground ml-2 font-normal">v{finding.version}</span>
                    </div>
                  </div>
                </div>
                <div className="h-8 w-px bg-border hidden md:block" />
                <div className="flex items-center gap-3">
                  <div className={`p-2 ${confidenceInfo.bg} rounded-md`}>
                    <Target className={`w-5 h-5 ${confidenceInfo.color}`} />
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">Confidence</div>
                    <div className="flex items-baseline gap-2">
                      <span className={`font-semibold ${confidenceInfo.color}`}>
                        {confidenceInfo.label}
                      </span>
                      <span className="text-sm text-muted-foreground">
                        ({Math.round(finding.confidence * 100)}%)
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left Column - Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Impact Section */}
            <div className="bg-card rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow">
              <div className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 bg-blue-500/10 rounded-lg">
                    <Info className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <h2 className="text-xl font-semibold text-foreground">Impact Analysis</h2>
                </div>
                <div className="pl-11">
                  <p className="text-foreground/90 leading-relaxed">{finding.impact}</p>
                </div>
              </div>
            </div>

            {/* Evidence Section */}
            <div className="bg-card rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow">
              <div className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 bg-orange-500/10 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-orange-600 dark:text-orange-400" />
                  </div>
                  <h2 className="text-xl font-semibold text-foreground">Evidence</h2>
                </div>
                <div className="space-y-3">
                  {finding.evidence.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-start gap-3 p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                    >
                      <div className="w-6 h-6 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span className="w-2 h-2 rounded-full bg-orange-600 dark:bg-orange-400" />
                      </div>
                      <span className="text-foreground/90 flex-1">{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Recommendations Section */}
            <div className="bg-card rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow">
              <div className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 bg-green-500/10 rounded-lg">
                    <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
                  </div>
                  <h2 className="text-xl font-semibold text-foreground">Recommended Actions</h2>
                </div>
                <div className="space-y-3">
                  {finding.recommendation.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-start gap-4 p-4 rounded-lg bg-muted/50 hover:bg-muted transition-colors group"
                    >
                      <div className="w-8 h-8 rounded-full bg-green-500/20 flex items-center justify-center flex-shrink-0 group-hover:bg-green-500/30 transition-colors">
                        <span className="text-sm font-bold text-green-600 dark:text-green-400">
                          {index + 1}
                        </span>
                      </div>
                      <span className="text-foreground/90 flex-1 pt-1">{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Sidebar */}
          <div className="space-y-6">
            {/* OWASP Mapping */}
            <div className="bg-card rounded-xl border border-border shadow-sm hover:shadow-md transition-shadow sticky top-6">
              <div className="p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="p-2 bg-purple-500/10 rounded-lg">
                    <Shield className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <h2 className="text-lg font-semibold text-foreground">OWASP Top 10</h2>
                </div>
                <div className="space-y-2">
                  {finding.owasp_mapping.map((code, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-3 rounded-lg bg-purple-500/10 border border-purple-500/20 hover:bg-purple-500/20 transition-colors"
                    >
                      <span className="font-bold text-purple-600 dark:text-purple-400">{code}</span>
                      <span className="text-xs text-muted-foreground">Security Misconfiguration</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Quick Stats */}
            <div className="bg-card rounded-xl border border-border shadow-sm">
              <div className="p-6">
                <h3 className="text-sm font-semibold text-muted-foreground mb-4">Quick Stats</h3>
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-foreground/70">Evidence Items</span>
                    <span className="text-lg font-bold text-foreground">{finding.evidence.length}</span>
                  </div>
                  <div className="h-px bg-border" />
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-foreground/70">Recommendations</span>
                    <span className="text-lg font-bold text-foreground">{finding.recommendation.length}</span>
                  </div>
                  <div className="h-px bg-border" />
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-foreground/70">OWASP Mappings</span>
                    <span className="text-lg font-bold text-foreground">{finding.owasp_mapping.length}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
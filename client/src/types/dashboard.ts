export interface StatCountDetails {
  users: number,
  projects: number,
  scans: number,
  findings: number,
  sbom_scans: number,
  sbom_findings: number
}

export interface CountTrend {
  pct: number;
  period: string;
}

export interface TopCountsTrend {
  users: CountTrend;
  projects: CountTrend;
  scans: CountTrend;
  sbom_scans: CountTrend;
}

export type SeverityData = {
  critical: number;
  high: number;
  medium: number;
  low: number;
};

type ScanStatus = {
  completed: number;
  in_progress: number;
  failed: number;
  queued: number;
};

export interface SystemStatus {
  counts: ScanStatus,
  total_scans: number
}

export interface LanguageDistributionItem {
  language: string;
  vulnerabilities: number;
  scans: number;
}

export interface FindingsTrendItem {
  date: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
  total: number;
}

export interface TopCweItem {
  id: string;
  name: string;
  count: number;
}

export interface ScansByProjectItem {
  project: string;
  scans: number;
  findings: number;
  critical: number;
}

export interface ScanDistributionItem {
  name: string;
  value: number;
  color: string;
}

export interface RecentScanItem {
  id: string;
  type: 'code' | 'sbom';
  project: string;
  scan_name: string;
  status: string;
  findings: number;
  created_at: string;
}

export interface DashboardResponse {
  top_counts: StatCountDetails,
  top_counts_trend: TopCountsTrend,
  system_status: SystemStatus,
  count_by_severity: SeverityData,
  language_distribution: LanguageDistributionItem[],
  findings_trend: FindingsTrendItem[],
  top_cwe: TopCweItem[],
  scans_by_project: ScansByProjectItem[],
  scan_distribution: ScanDistributionItem[],
  recent_scans: RecentScanItem[]
}

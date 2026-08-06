interface FolderMetrics {
    total_loc: number,
    total_functions: number,
    languages: string[]
}
export interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface ScanDetails {
  id: string;
  project_id: string;
  scan_name: string;
  status: string;
  findings: number;
  total_files: number;
  files_scanned: number;
  created_at: string;
  end_time: string | null;
  triggered_by: string;
  metrics: FolderMetrics;
  error?: string;
  severity_counts?: SeverityCounts;
}
 
export interface SbomScanDetails {
  id: string;
  project_id: string;
  scan_name: string;
  status: string;
  vulnerabilities: number;
  total_files: number;
  dependencies_scanned: number;
  severity_counts: {
    critical: number,
    high: number,
    medium: number,
    low: number,
    negligible: number
  };
  sbom_format: string;
  ecosystems: string[];
  created_at: string;
  end_time: string | null;
  triggered_by: string;
}

export interface CreateScanDetails {
  project_id: string;
  scan_type: string;
  scan_name: string;
  zip_file: File | null;
  zip_error?: string;
}

export interface CreateSBOMScanForm {
  project_id: string;
  scan_name: string;
  file: File | null;
  file_error?: string;
}
 
export interface CreateGithubScans {
  project_id: string;
  scan_name: string;
  scan_type: string;
  git_token: string;
  git_repo: string;
  git_rowner: string;
}
 
export interface UpdateProjectDetails {
  name?: string;
  preset?: string;
  description?: string;
}
 
export interface ScanListResponse {
  scans: ScanDetails[];
  pagination: {
    total: number;
    page: number;
    limit: number;
    pages: number;
  }
}

export interface SbomScanListResponse {
  scans: SbomScanDetails[];
  pagination: {
    total: number;
    page: number;
    limit: number;
    pages: number;
  }
}
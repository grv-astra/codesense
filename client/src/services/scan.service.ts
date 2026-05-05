import { BaseApiClient } from "@/lib/api";
import type { CreateGithubScans, CreateSBOMScanForm, CreateScanDetails, SbomScanDetails, SbomScanListResponse, ScanDetails, ScanListResponse } from "@/types/scan";

class ScanService extends BaseApiClient {
  async getScanById(scanId: string): Promise<ScanDetails> {
    return this.get<ScanDetails>(`api/scans/${scanId}`);
  }

  async getSbomScanById(scanId: string): Promise<SbomScanDetails> {
    return this.get<SbomScanDetails>(`api/scans/sbom/${scanId}`);
  }

  async startScan(data: CreateScanDetails): Promise<ScanDetails> {
    const formData = new FormData();
    formData.append("scan_name", data.scan_name);
    formData.append("project_id", data.project_id);
    if (data.zip_file) {
      formData.append("zip_file", data.zip_file);
    }

    return this.post<ScanDetails>("api/scans/create/", formData);
  }

  async startSbomZipScan(data: CreateScanDetails): Promise<SbomScanDetails> {
    const formData = new FormData();
    formData.append("scan_name", data.scan_name);
    formData.append("project_id", data.project_id);
    if (data.zip_file) {
      formData.append("zip_file", data.zip_file);
    }

    return this.post<SbomScanDetails>("api/scans/sbom/create/", formData);
  }

  async startSbomFileScan(data: CreateSBOMScanForm): Promise<SbomScanDetails> {
    const formData = new FormData();
    formData.append("scan_name", data.scan_name);
    formData.append("project_id", data.project_id);
    if (data.file) {
      formData.append("sbom_file", data.file);
    }
    return this.post<SbomScanDetails>("api/scans/grype/create/", formData);
  }

  async startGithubScan(data: CreateGithubScans): Promise<ScanDetails> {
    return this.post<ScanDetails>("api/scans/create/", data);
  }

  async getScanByProject(projectId: string, params?: { type?: string, page?: number; limit?: number; search?: string }): Promise<ScanListResponse | SbomScanListResponse> {
    return this.get<any>(`api/scans/project/${projectId}/`, params);
  }

  async deleteScan(scanId: string): Promise<void> {
    return this.delete<void>(`api/scans/delete/${scanId}/`);
  }

  async deleteSbomScan(scanId: string): Promise<void> {
    return this.delete<void>(`api/scans/sbom/delete/${scanId}/`);
  }
  
  async downloadCsv(scanId: string): Promise<any> {
    return this.axiosInstance.get<any>(`api/findings/scan/csv/${scanId}/`, {
      responseType: "blob"
    });
  }

  async downloadSbomCsv(scanId: string): Promise<any> {
    return this.axiosInstance.get<any>(`api/findings/scan/sbom/csv/${scanId}/`, {
      responseType: "blob"
    });
  }
}

export const scanService = new ScanService();
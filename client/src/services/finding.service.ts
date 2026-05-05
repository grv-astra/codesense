import { BaseApiClient } from "@/lib/api";
import type { FindingDetails, FindingListResponse, LicensesListResponse, UpdateFindingDetails } from "@/types/finding";

class FindingService extends BaseApiClient {
  async getFindingById(findingId: string): Promise<FindingDetails> {
    return this.get<FindingDetails>(`api/findings/${findingId}/`);
  }

  async getFindingsByScan(scanId: string, params?: { page?: number; limit?: number; search?: string }): Promise<FindingListResponse> {
    return this.get<FindingListResponse>(`api/findings/scan/${scanId}/`, params);
  }

  async getSbomFindingsByScan(scanId: string, params?: { page?: number; limit?: number; search?: string }): Promise<FindingListResponse> {
    return this.get<FindingListResponse>(`api/findings/scan/sbom/${scanId}/`, params);
  }

   async getSbomLicensesByScan(scanId: string, params?: { page?: number; limit?: number; search?: string }): Promise<LicensesListResponse> {
    return this.get<LicensesListResponse>(`api/findings/sbom/licenses/${scanId}/`, params);
  }

  async updateFinding(findingId: string,  data: UpdateFindingDetails): Promise<FindingDetails> {
    return this.patch<FindingDetails>(`api/findings/${findingId}/`, data);
  }

  async toggleApproveFinding(findingId: string): Promise<{id: string, approved: boolean}> {
    return this.patch<{id: string, approved: boolean}>(`api/findings/approve/${findingId}/`);
  }

  async deleteFinding(findingId: string): Promise<void> {
    return this.delete<void>(`api/findings/delete/${findingId}/`);
  }
}

export const findingService = new FindingService();
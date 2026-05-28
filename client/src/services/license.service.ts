import { BaseApiClient } from '@/lib/api';
import type { LicenseStatus } from '@/types/license';

class LicenseService extends BaseApiClient {
  async getStatus(): Promise<LicenseStatus> {
    return this.get<LicenseStatus>('/api/license/');
  }
}

export const licenseService = new LicenseService();

import { BaseApiClient } from '@/lib/api';
import type { TrialStatus } from '@/types/trial';

class TrialService extends BaseApiClient {
  async getStatus(): Promise<TrialStatus> {
    return this.get<TrialStatus>('/api/trial/');
  }
}

export const trialService = new TrialService();

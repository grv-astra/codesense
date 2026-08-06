import { BaseApiClient } from "@/lib/api";

export interface ActivationStatus {
  configured: boolean;
  activated: boolean;
}

class ActivationService extends BaseApiClient {
  async getStatus(): Promise<ActivationStatus> {
    return this.get<ActivationStatus>('/api/activation/');
  }

  async activate(password: string): Promise<{ activated: boolean; detail?: string }> {
    return this.post<{ activated: boolean; detail?: string }>('/api/activation/', { password });
  }
}

export const activationService = new ActivationService();

import { BaseApiClient } from '@/lib/api';

export interface SetupStatus {
  setup_needed: boolean;
}

export interface CreateAdminInput {
  email: string;
  password: string;
  name: string;
  company?: string;
}

class SetupService extends BaseApiClient {
  async getStatus(): Promise<SetupStatus> {
    return this.get<SetupStatus>('/api/auth/setup/');
  }

  async createAdmin(data: CreateAdminInput): Promise<{ user: unknown }> {
    return this.post<{ user: unknown }>('/api/auth/setup/admin/', data);
  }
}

export const setupService = new SetupService();

// client/src/services/apikey.service.ts
import { BaseApiClient } from "@/lib/api";
import type { ApiKeyDetails, CreateApiKeyPayload, CreateApiKeyResponse } from "@/types/apiKey";

class ApiKeyService extends BaseApiClient {
  async listApiKeys(projectId: string): Promise<ApiKeyDetails[]> {
    return this.get<ApiKeyDetails[]>(`api/projects/${projectId}/api-keys/`);
  }

  async createApiKey(projectId: string, data: CreateApiKeyPayload): Promise<CreateApiKeyResponse> {
    return this.post<CreateApiKeyResponse>(`api/projects/${projectId}/api-keys/`, data);
  }

  async revokeApiKey(projectId: string, keyId: string): Promise<ApiKeyDetails> {
    return this.post<ApiKeyDetails>(`api/projects/${projectId}/api-keys/${keyId}/revoke/`);
  }
}

export const apiKeyService = new ApiKeyService();

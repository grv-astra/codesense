// client/src/types/apiKey.ts
export interface ApiKeyDetails {
  id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface CreateApiKeyResponse extends ApiKeyDetails {
  key: string;
}

export interface CreateApiKeyPayload {
  name: string;
}

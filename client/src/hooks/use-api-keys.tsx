// client/src/hooks/use-api-keys.tsx
import { apiKeyService } from '@/services/apikey.service';
import type { CreateApiKeyPayload } from '@/types/apiKey';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export function useApiKeys(projectId: string) {
  return useQuery({
    queryKey: ['api-keys', projectId],
    queryFn: () => apiKeyService.listApiKeys(projectId),
    enabled: !!projectId,
  });
}

export function useCreateApiKey(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateApiKeyPayload) => apiKeyService.createApiKey(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys', projectId] });
    },
  });
}

export function useRevokeApiKey(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) => apiKeyService.revokeApiKey(projectId, keyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys', projectId] });
    },
  });
}

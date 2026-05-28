import { setupService, type CreateAdminInput } from '@/services/setup.service';
import { useMutation, useQuery } from '@tanstack/react-query';

export function useSetupStatus() {
  return useQuery({
    queryKey: ['setup'],
    queryFn: () => setupService.getStatus(),
    retry: false,
    staleTime: 0,
  });
}

export function useCreateInitialAdmin() {
  return useMutation({
    mutationFn: (data: CreateAdminInput) => setupService.createAdmin(data),
  });
}

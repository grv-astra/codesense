import { licenseService } from '@/services/license.service';
import { useQuery } from '@tanstack/react-query';

export function useLicenseStatus() {
  return useQuery({
    queryKey: ['license'],
    queryFn: () => licenseService.getStatus(),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 30 * 60 * 1000, // re-check every 30 min so the banner stays current
  });
}

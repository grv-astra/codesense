import { trialService } from '@/services/trial.service';
import { useQuery } from '@tanstack/react-query';
import type { TrialStatus } from '@/types/trial';

export function useTrialStatus() {
  return useQuery({
    queryKey: ['trial'],
    queryFn: () => trialService.getStatus(),
    staleTime: 10 * 1000,            // short: the count changes as scans complete
    refetchOnWindowFocus: true,
  });
}

// Convenience: true only when trial mode is on AND this scan type's
// allowance is used up -- code and SBOM are independent, so check the type
// you're actually about to start.
export function isTrialExhausted(t: TrialStatus | undefined, scanType: 'code' | 'sbom') {
  return !!t?.trial_mode && (t[scanType].remaining ?? 1) <= 0;
}

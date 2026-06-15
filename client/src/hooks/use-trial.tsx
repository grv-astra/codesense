import { trialService } from '@/services/trial.service';
import { useQuery } from '@tanstack/react-query';

export function useTrialStatus() {
  return useQuery({
    queryKey: ['trial'],
    queryFn: () => trialService.getStatus(),
    staleTime: 10 * 1000,            // short: the count changes as scans complete
    refetchOnWindowFocus: true,
  });
}

// Convenience: true only when trial mode is on AND no scans remain.
export function isTrialExhausted(t?: { trial_mode: boolean; remaining: number | null }) {
  return !!t?.trial_mode && (t.remaining ?? 1) <= 0;
}

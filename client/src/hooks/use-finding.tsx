import { findingService } from "@/services/finding.service";
import type { FindingDetails } from "@/types/finding";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useFindingDetails(findingId: string) {
  return useQuery({
    queryKey: ['findings', findingId],
    queryFn: () => findingService.getFindingById(findingId),
    enabled: !!findingId,
  });
}

export function useUpdateFinding() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ findingId, findingData }: { findingId: string; findingData: FindingDetails }) =>
      findingService.updateFinding(findingId, findingData),
    onSuccess: (data) => {
      queryClient.setQueryData(['findings', data.id], data);
      queryClient.invalidateQueries({ queryKey: ['findings', 'list'] });
    },
  });
}

export function useDeleteFinding() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (findingId: string) => 
      findingService.deleteFinding(findingId),
    onSuccess: () => {
      queryClient.invalidateQueries({queryKey: ['findings', 'list']})
    },
  });
}

export function useToggleFindingApproved() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (findingId: string) => 
      findingService.toggleApproveFinding(findingId),
    onSuccess: () => {
      queryClient.invalidateQueries({queryKey: ['findings', 'list']})
    },
  });
}


// export function useCreateFinding() {
//   const queryClient = useQueryClient();

//   return useMutation({
//     mutationFn: (findingData: CreateFindingDetails) => findingService.updateFinding(findingData),
//     onSuccess: () => {
//       // Invalidate and refetch users list
//       queryClient.invalidateQueries({ queryKey: ['findings', 'list'] });
//     },
//     onError: (error) => {
//       console.error('Failed to create user:', error);
//     },
//   });
// }

export function useFindings(scanId: string, params?: { page?: number; limit?: number; search?: string }) {
  return useQuery({
    queryKey: ['findings', 'list', scanId, params],
    queryFn: () => findingService.getFindingsByScan(scanId, params),
  });
}

export function useSbomFindings(scanId: string, params?: { page?: number; limit?: number; search?: string }) {
  return useQuery({
    queryKey: ['findings', 'sbom', 'list', scanId, params],
    queryFn: () => findingService.getSbomFindingsByScan(scanId, params),
  });
}

export function useSbomLicenses(scanId: string, params?: { page?: number; limit?: number; search?: string }) {
  return useQuery({
    queryKey: ['licenses', 'sbom', 'list', scanId, params],
    queryFn: () => findingService.getSbomLicensesByScan(scanId, params),
  });
}

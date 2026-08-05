
import { scanService } from '@/services/scan.service';
import type { CreateGithubScans, CreateSBOMScanForm, CreateScanDetails } from '@/types/scan';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

// Poll while a scan is running so the updates page reflects live progress
// (status, findings count, completion) without a manual refresh; stop once the
// scan reaches a terminal state. 'interrupted' stops here too -- the pipeline
// isn't making progress anymore until a user explicitly resumes it.
const TERMINAL_STATUSES = ['completed', 'failed', 'cancelled', 'interrupted'];
const SCAN_POLL_MS = 2500;

export function useScanDetails(scanId: string) {
  return useQuery({
    queryKey: ['scans', scanId],
    queryFn: () => scanService.getScanById(scanId),
    enabled: !!scanId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL_STATUSES.includes(status) ? false : SCAN_POLL_MS;
    },
    refetchIntervalInBackground: true,
  });
}

export function useSbomScanDetails(scanId: string) {
  return useQuery({
    queryKey: ['scans', scanId],
    queryFn: () => scanService.getSbomScanById(scanId),
    enabled: !!scanId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL_STATUSES.includes(status) ? false : SCAN_POLL_MS;
    },
    refetchIntervalInBackground: true,
  });
}


export function useScans(projectId: string, params?: { type?: string, page?: number; limit?: number; search?: string }) {
  return useQuery({
    queryKey: ['scans', 'list', projectId, params],
    queryFn: () => scanService.getScanByProject(projectId, params),
  });
}

export function useSbomScans(projectId: string, params?: { page?: number; limit?: number; search?: string }) {
  return useQuery({
    queryKey: ['scans', 'list', projectId, params],
    queryFn: () => scanService.getScanByProject(projectId, params),
  });
}

export function useDeleteScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (scanId: string) =>
      scanService.deleteScan(scanId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans', 'list'] });
    },
  });
}

export function useCancelScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (scanId: string) => scanService.cancelScan(scanId),
    onSuccess: (_data, scanId) => {
      queryClient.invalidateQueries({ queryKey: ['scans', scanId] });
      queryClient.invalidateQueries({ queryKey: ['scans', 'list'] });
    },
  });
}

export function useResumeScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (scanId: string) => scanService.resumeScan(scanId),
    onSuccess: (_data, scanId) => {
      queryClient.invalidateQueries({ queryKey: ['scans', scanId] });
      queryClient.invalidateQueries({ queryKey: ['scans', 'list'] });
    },
  });
}

export function useDeleteSbomScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (scanId: string) =>
      scanService.deleteSbomScan(scanId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans', 'list'] });
    },
  });
}
export function useCreateScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (scanData: CreateScanDetails) => scanService.startScan(scanData),
    onSuccess: () => {
      // Invalidate and refetch users list
      queryClient.invalidateQueries({ queryKey: ['scans', 'list'] });
    },
    onError: (error) => {
      console.error('Failed to create user:', error);
    },
  });
}

export function useSbomScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (scanData: CreateSBOMScanForm) => scanService.startSbomFileScan(scanData),
    onSuccess: () => {
      // Invalidate and refetch users list
      queryClient.invalidateQueries({ queryKey: ['scans', 'list'] });
    },
    onError: (error) => {
      console.error('Failed to create user:', error);
    },
  });
}

export function useCreateSbomScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (scanData: CreateScanDetails) => scanService.startSbomZipScan(scanData),
    onSuccess: () => {
      // Invalidate and refetch users list
      queryClient.invalidateQueries({ queryKey: ['scans', 'list'] });
    },
    onError: (error) => {
      console.error('Failed to create user:', error);
    },
  });
}

export function useCreateGithubScan() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (scanData: CreateGithubScans) => scanService.startGithubScan(scanData),
    onSuccess: () => {
      // Invalidate and refetch users list
      queryClient.invalidateQueries({ queryKey: ['scans', 'list'] });
    },
    onError: (error) => {
      console.error('Failed to create user:', error);
    },
  });
}

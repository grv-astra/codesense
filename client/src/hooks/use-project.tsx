
import { projectService } from '@/services/project.service';
import type { CreateProjectDetails } from '@/types/project';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export function useProjectDetails(projectId: string) {
  return useQuery({
    queryKey: ['projects', projectId],
    queryFn: () => projectService.getProjectById(projectId),
    enabled: !!projectId,
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, projectData }: { projectId: string; projectData: any }) =>
      projectService.updateProject(projectId, projectData),
    onSuccess: (data) => {
      queryClient.setQueryData(['projects', data.id], data);
      queryClient.invalidateQueries({ queryKey: ['projects', 'list'] });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (projectId: string) =>
      projectService.deleteProject(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects', 'list'] });
    },
    onError: (error) => {
      console.error('Failed to update user:', error);
    },
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (projectData: CreateProjectDetails) => projectService.createProject(projectData),
    onSuccess: () => {
      // Invalidate and refetch users list
      queryClient.invalidateQueries({ queryKey: ['projects', 'list'] });
      queryClient.invalidateQueries({ queryKey: ['projects', 'names'] });
    },
    onError: (error) => {
      console.error('Failed to create user:', error);
    },
  });
}

export function useProjectNames() {
  return useQuery({
    queryKey: ['projects', 'names'],
    queryFn: () => projectService.getNames(),
  });
}

export function useProjects(params?: { page?: number; limit?: number; search?: string }) {
  return useQuery({
    queryKey: ['projects', 'list', params],
    queryFn: () => projectService.getProjectsList(params),
  });
}

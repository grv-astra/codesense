import { userService } from '@/services/user.service';
import type { RegisterCredentials, UpdateUserCredentials } from '@/types/auth';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

export function useUserProfile(userId: string) {
  return useQuery({
    queryKey: ['users', userId],
    queryFn: () => userService.getUserProfile(userId),
    enabled: !!userId,
  });
}

export function useUsers(params?: { page?: number; limit?: number; search?: string }) {
  return useQuery({
    queryKey: ['users', 'list', params],
    queryFn: () => userService.getUsersList(params),
  });
}

export function useDeleteProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userId: string) =>
      userService.deleteUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users', 'list'] });
    },
    onError: (error) => {
      console.error('Failed to update user:', error);
    },
  });
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: UpdateUserCredentials }) =>
      userService.updateProfile(userId, data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({queryKey: ['user']})
      queryClient.setQueryData(['users', data.id], data);
      queryClient.invalidateQueries({ queryKey: ['users', 'list'] });
    },
    onError: (error) => {
      console.error('Failed to update user:', error);
    },
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (userData: RegisterCredentials) => userService.createProfile(userData),
    onSuccess: () => {
      // Invalidate and refetch users list
      queryClient.invalidateQueries({ queryKey: ['users', 'list'] });
    },
    onError: (error) => {
      console.error('Failed to create user:', error);
    },
  });
}

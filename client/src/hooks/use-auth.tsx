import { authService as authServiceSingleton } from '@/lib/auth';
import { authService } from '@/services/auth.service';
import { generalService } from '@/services/general.service';
import type { LoginCredentials, PermissionRole, RolePermissions } from '@/types/auth';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from '@tanstack/react-router';

export function useAuth() {
  const queryClient = useQueryClient();
  const router = useRouter();

  const {
    data: user,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['user'],
    queryFn: async () => {
      try {
        const user = await authService.getMe();
        authServiceSingleton.setUser(user);
        return user;
      } catch (error) {
        authServiceSingleton.logout();
        authService.clearToken();
        throw error;
      }
    },
    enabled: authServiceSingleton.isAuth(),
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  const loginMutation = useMutation({
    mutationFn: (credentials: LoginCredentials) => authService.login(credentials),
    onSuccess: (data) => {
      authService.setToken(data.token);
      authServiceSingleton.setUser(data.user);
      queryClient.setQueryData(['user'], data.user);
      router.navigate({ to: '/' });
    },
    onError: (error) => {
      console.error('Login failed:', error);
    },
  });

  const logoutMutation = useMutation({
    mutationFn: () => authService.logout(),
    onSettled: () => {
      authServiceSingleton.logout();
      authService.clearToken();
      queryClient.clear();
      router.navigate({ to: '/login' });
    },
  });

  return {
    user,
    isLoading,
    error,
    isAuthenticated: authServiceSingleton.isAuth(),
    login: loginMutation.mutate,
    logout: logoutMutation.mutate,
    isLoginLoading: loginMutation.isPending,
    loginError: loginMutation.error,
  };
}

export function usePermissions(selectedRole: PermissionRole) {
  return useQuery({
    queryKey: ['permissions', selectedRole],
    queryFn: () => generalService.fetchPermissionsByRole(selectedRole),
    enabled: !!selectedRole,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useUpdatePermissions() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: RolePermissions) =>
      generalService.updatePermissions(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['permissions', data.role]});
    }
  });
}

export function useMyPermissionsQuery() {
  return useQuery({
    queryKey: ['userPermissions'],
    queryFn: () => generalService.fetchMyPermissions(),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });
}

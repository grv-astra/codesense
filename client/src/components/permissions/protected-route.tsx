import React from 'react';
import { useMyPermissionsQuery } from '@/hooks/use-auth';
import type { AllPermissions } from '@/types/auth';
import { hasAllPermissions, hasAnyPermission } from '@/utils/permissions';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermissions: (keyof AllPermissions)[];
  requireAll?: boolean;
  fallback?: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredPermissions,
  requireAll = false,
  fallback = <div>Access denied. You don't have permission to view this page.</div>
}) => {
  const { data: userRole, isLoading, error } = useMyPermissionsQuery();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (error) {
    return <div>Error loading permissions</div>;
  }

  if (!userRole) {
    return fallback;
  }

  const hasPermission = requireAll
    ? hasAllPermissions(userRole.permissions, requiredPermissions)
    : hasAnyPermission(userRole.permissions, requiredPermissions);

  if (!hasPermission) {
    return fallback;
  }

  return <>{children}</>;
};
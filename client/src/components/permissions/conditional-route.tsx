import { useMyPermissionsQuery } from '@/hooks/use-auth';
import type { AllPermissions } from '@/types/auth';
import { checkPermission, hasAllPermissions, hasAnyPermission } from '@/utils/permissions';
import React from 'react';

interface ConditionalRenderProps {
  children: React.ReactNode;
  permission?: keyof AllPermissions;
  permissions?: (keyof AllPermissions)[];
  requireAll?: boolean;
}

export const ConditionalRender: React.FC<ConditionalRenderProps> = ({
  children,
  permission,
  permissions,
  requireAll = false
}) => {
  const { data: userRole } = useMyPermissionsQuery();

  if (!userRole) return null;

  let hasAccess = false;

  if (permission) {
    hasAccess = checkPermission(userRole.permissions, permission);
  } else if (permissions) {
    hasAccess = requireAll
      ? hasAllPermissions(userRole.permissions, permissions)
      : hasAnyPermission(userRole.permissions, permissions);
  }

  return hasAccess ? <>{children}</> : null;
};

import type { AllPermissions } from "@/types/auth";


export const checkPermission = (
  permissions: AllPermissions | undefined,
  permission: keyof AllPermissions
): boolean => {
  if (!permissions) return false;
  return permissions[permission] === true;
};

export const hasAnyPermission = (
  permissions: AllPermissions | undefined,
  requiredPermissions: (keyof AllPermissions)[]
): boolean => {
  if (!permissions) return false;
  return requiredPermissions.some(permission => permissions[permission] === true);
};

export const hasAllPermissions = (
  permissions: AllPermissions | undefined,
  requiredPermissions: (keyof AllPermissions)[]
): boolean => {
  if (!permissions) return false;
  return requiredPermissions.every(permission => permissions[permission] === true);
};

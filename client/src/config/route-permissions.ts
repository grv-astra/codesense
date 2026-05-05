import type { AllPermissions } from '@/types/auth';

export interface RoutePermissionConfig {
  path: string;
  requiredPermissions: (keyof AllPermissions)[];
  requireAll?: boolean;
}

export const routePermissions: RoutePermissionConfig[] = [
  // Project routes
  {
    path: '/project/list',
    requiredPermissions: ['view_projects']
  },
  {
    path: '/project/new',
    requiredPermissions: ['create_project']
  },
  {
    path: '/project/$projectId',
    requiredPermissions: ['view_scans']
  },
  {
    path: '/project/$projectId/edit',
    requiredPermissions: ['update_project']
  },
  
  // Scan routes
  {
    path: '/scan/start',
    requiredPermissions: ['create_scan']
  },
  {
    path: '/scan/$scanId',
    requiredPermissions: ['view_scans']
  },
  {
    path: '/scan/$scanId/findings',
    requiredPermissions: ['view_findings']
  },
  {
    path: '/scan/$scanId/updates',
    requiredPermissions: ['view_scans']
  },
  
  // Finding routes
  {
    path: '/finding/$findingId',
    requiredPermissions: ['view_findings']
  },
  
  // User management routes (assuming admin permissions)
  {
    path: '/users/list',
    requiredPermissions: ['view_projects'], // Adjust based on your admin permissions
  },
  {
    path: '/users/new',
    requiredPermissions: ['create_project'], // Adjust based on your admin permissions
  }
];

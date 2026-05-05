import { BaseApiClient } from "@/lib/api";
import type { RolePermissions, PermissionRole } from "@/types/auth";
import type { DashboardResponse } from "@/types/dashboard";

class GeneralService extends BaseApiClient {
  async fetchDashboard(): Promise<DashboardResponse> {
    return this.get<DashboardResponse>('/api/dashboard/');
  }

  async fetchPermissionsByRole(role: PermissionRole): Promise<RolePermissions> {
    return this.get<RolePermissions>(`/api/auth/permissions/${role}`);
  }

  async updatePermissions(data: RolePermissions): Promise<RolePermissions> {
    return this.post<RolePermissions>('/api/auth/permissions/update/', data);
  }

  async fetchMyPermissions(): Promise<RolePermissions>{
    return this.get<RolePermissions>('/api/auth/permissions/me');
  }
}

export const generalService = new GeneralService();

import { BaseApiClient } from "@/lib/api";
import type { CreateProjectDetails, ProjectDetails, ProjectListResponse, UpdateProjectDetails } from "@/types/project";

class ProjectService extends BaseApiClient {
  async getProjectById(projectId: string): Promise<ProjectDetails> {
    return this.get<ProjectDetails>(`api/projects/${projectId}`);
  }

  async getNames(): Promise<{id: string, name: string}[]> {
    return this.get<{id: string, name: string}[]>(`api/projects/names`);
  }

  async createProject(data: CreateProjectDetails): Promise<ProjectDetails> {
    return this.post<ProjectDetails>(`api/projects/create/`, data);
  }

  async updateProject(projectId: string, data: UpdateProjectDetails): Promise<ProjectDetails> {
    return this.patch<ProjectDetails>(`api/projects/${projectId}/`, data);
  }

  async getProjectsList(params?: { page?: number; limit?: number; search?: string }): Promise<ProjectListResponse> {
    return this.get<any>('api/projects/', params);
  }

  async deleteProject(projectId: string): Promise<void> {
    return this.delete<void>(`api/projects/${projectId}/`);
  }
}

export const projectService = new ProjectService();
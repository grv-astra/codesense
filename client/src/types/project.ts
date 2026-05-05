export interface ProjectDetails {
  id: string;
  name: string;
  preset: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectDetails {
  name: string;
  preset: string;
  description: string;
}

export interface UpdateProjectDetails {
  name?: string;
  preset?: string;
  description?: string;
}

export interface ProjectListResponse {
  projects: ProjectDetails[];
  pagination: {
    total: number;
    page: number;
    limit: number;
    pages: number;
  }
}
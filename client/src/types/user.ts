export interface UserProfile {
  id: string;
  company: string,
  email: string;
  name: string;
  role: 'superuser' | 'admin' | 'manager' | 'user';
  created_at: string | null;
  updated_at: string | null;
}

export interface UpdateUserData {
  name?: string;
  bio?: string;
}

export interface UserListResponse {
  users: UserProfile[];
  pagination: {
    total: number;
    page: number;
    limit: number;
    pages: number;
  }
}
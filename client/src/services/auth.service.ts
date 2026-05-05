import { BaseApiClient } from "@/lib/api";
import type { AuthResponse, LoginCredentials, User } from "@/types/auth";

class AuthService extends BaseApiClient {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    return this.post<AuthResponse>('/api/auth/login/', credentials);
  }

  async getMe(): Promise<User> {
    return this.get<User>('/api/auth/me/');
  }

  async logout(): Promise<void> {
    return this.post<void>('/auth/auth/logout');
  }

  async refreshToken(): Promise<AuthResponse> {
    return this.post<AuthResponse>('/auth/refresh');
  }
}

export const authService = new AuthService();

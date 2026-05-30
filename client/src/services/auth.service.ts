import { BaseApiClient } from "@/lib/api";
import type { AuthResponse, LoginCredentials, User } from "@/types/auth";

class AuthService extends BaseApiClient {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    return this.post<AuthResponse>('/api/auth/login/', credentials);
  }

  async getMe(): Promise<User> {
    return this.get<User>('/api/auth/me/');
  }

  // NOTE: the backend does not implement server-side logout/refresh (JWT is
  // stateless). Logout still works because useAuth clears the token in onSettled
  // regardless of this call. Paths are kept well-formed for when/if the backend
  // adds these endpoints.
  async logout(): Promise<void> {
    return this.post<void>('/api/auth/logout/');
  }

  async refreshToken(): Promise<AuthResponse> {
    return this.post<AuthResponse>('/api/auth/refresh/');
  }
}

export const authService = new AuthService();

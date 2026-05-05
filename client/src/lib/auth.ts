import type { User } from '@/types/auth';
import { redirect } from '@tanstack/react-router';

export class AuthService {
  private static instance: AuthService;
  private user: User | null = null;
  private isAuthenticated: boolean = false;

  private constructor() {
    this.checkAuthState();
  }

  static getInstance(): AuthService {
    if (!AuthService.instance) {
      AuthService.instance = new AuthService();
    }
    return AuthService.instance;
  }

  private checkAuthState() {
    const token = localStorage.getItem('auth_token');
    this.isAuthenticated = !!token;
  }

  getUser(): User | null {
    return this.user;
  }

  setUser(user: User | null) {
    this.user = user;
    this.isAuthenticated = !!user;
  }

  isAuth(): boolean {
    return this.isAuthenticated;
  }

  logout() {
    this.user = null;
    this.isAuthenticated = false;
    localStorage.removeItem('auth_token');
  }

  requireAuth() {
    if (!this.isAuthenticated) {
      throw redirect({ to: '/login' });
    }
  }

  requireGuest() {
    if (this.isAuthenticated) {
      throw redirect({ to: '/' });
    }
  }
}

export const authService = AuthService.getInstance();
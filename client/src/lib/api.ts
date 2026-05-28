import axios, { type AxiosInstance, type AxiosResponse, AxiosError } from 'axios';

// Fixed loopback backend. Works both in the dev browser and inside the Tauri
// webview, whose origin is tauri://localhost — so window.location.hostname
// (the old value) resolved to "tauri.localhost" and broke every request.
// Overridable at build/runtime via VITE_BACKEND_URL.
const port = 8585;
export const BACKEND_URL =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? `http://127.0.0.1:${port}`;

// Base API Client with common functionality
export class BaseApiClient {
  protected axiosInstance: AxiosInstance;
  
  constructor() {
    this.axiosInstance = axios.create({
      baseURL: BACKEND_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Initialize token from localStorage
    const token = localStorage.getItem('auth_token');
    if (token) {
      this.setToken(token);
    }

    this.axiosInstance.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }

        // 🚨 Remove 'Content-Type' if sending FormData
        if (
          config.data instanceof FormData &&
          config.headers &&
          config.headers['Content-Type']
        ) {
          delete config.headers['Content-Type'];
        }

        return config;
      },
      (error) => Promise.reject(error)
    );


    // Response interceptor for error handling
    this.axiosInstance.interceptors.response.use(
      (response: AxiosResponse) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          this.clearToken();
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  setToken(token: string) {
    localStorage.setItem('auth_token', token);
    this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }

  clearToken() {
    localStorage.removeItem('auth_token');
    delete this.axiosInstance.defaults.headers.common['Authorization'];
  }

  // Generic CRUD methods that can be used by all services
  protected async get<T>(endpoint: string, params?: any): Promise<T> {
    const response = await this.axiosInstance.get<T>(endpoint, { params });
    return response.data;
  }

  protected async post<T>(endpoint: string, data?: any, customHeaders?: Record<string, string>): Promise<T> {
    const isFormData = typeof FormData !== "undefined" && data instanceof FormData;
    const headers = {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...customHeaders
    };

    const response = await this.axiosInstance.post<T>(endpoint, data, { headers });
    return response.data;
  }

  protected async put<T>(endpoint: string, data?: any): Promise<T> {
    const response = await this.axiosInstance.put<T>(endpoint, data);
    return response.data;
  }

  protected async patch<T>(endpoint: string, data?: any): Promise<T> {
    const response = await this.axiosInstance.patch<T>(endpoint, data);
    return response.data;
  }

  protected async delete<T>(endpoint: string): Promise<T> {
    const response = await this.axiosInstance.delete<T>(endpoint);
    return response.data;
  }
}
import axios, { type AxiosInstance, type AxiosResponse, AxiosError } from 'axios';

const ip = window.location.hostname;
const port = 8585; // adjust if needed
export const BACKEND_URL = `http://${ip}:${port}`;

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
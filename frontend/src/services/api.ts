import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosRequestHeaders,
} from 'axios';
import { setupInterceptors } from './interceptors';

// Create the underlying Axios instance
const raw: AxiosInstance = axios.create({
  baseURL: '/api',
  headers: { Accept: 'application/json' },
});

// Setup interceptors (transforms responses to response.data)
setupInterceptors(raw);

// Typed wrapper so callers receive T (not AxiosResponse<T>)
type ApiClient = {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<T>;
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T>;
};

const api: ApiClient = {
  get: <T>(url: string, config?: AxiosRequestConfig) =>
    raw.get<T>(url, config).then((res) => res as unknown as T),
  post: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) => {
    let finalConfig = config;
    if (typeof FormData !== 'undefined' && data instanceof FormData) {
      const headers = { ...(config?.headers ?? {}) } as AxiosRequestHeaders;
      delete headers['Content-Type'];
      delete headers['content-type'];
      finalConfig = { ...(config ?? {}), headers };
    }
    return raw.post<T>(url, data, finalConfig).then((res) => res as unknown as T);
  },
  put: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    raw.put<T>(url, data, config).then((res) => res as unknown as T),
  patch: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
    raw.patch<T>(url, data, config).then((res) => res as unknown as T),
  delete: <T>(url: string, config?: AxiosRequestConfig) =>
    raw.delete<T>(url, config).then((res) => res as unknown as T),
};

export default api;

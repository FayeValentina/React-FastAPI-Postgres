import { AxiosInstance } from 'axios';
import { authManager } from './authManager';
import { uiManager } from './uiManager';

/**
 * 正在刷新 token 的 Promise，用于避免并发刷新
 */
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (error?: unknown) => void;
}> = [];

/**
 * 处理等待队列中的请求
 */
const processQueue = (error: unknown) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve();
    }
  });
  
  failedQueue = [];
};

/**
 * 设置 Axios 拦截器
 */
export function setupInterceptors(api: AxiosInstance): void {
  
  // 请求拦截器：添加 Authorization header
  api.interceptors.request.use(
    (config) => {
      // 不需要认证的端点
      const publicEndpoints = [
        '/v1/auth/login',
        '/v1/auth/register', 
        '/v1/auth/refresh',
        '/v1/auth/forgot-password',
        '/v1/auth/verify-reset-token',
        '/v1/auth/reset-password'
      ];
      
      const isPublicEndpoint = publicEndpoints.some(endpoint => 
        config.url?.includes(endpoint)
      );
      
      // 只为受保护的端点添加 token
      if (!isPublicEndpoint) {
        const accessToken = authManager.getAccessToken();
        if (accessToken) {
          config.headers.Authorization = `Bearer ${accessToken}`;
        }
      }
      
      return config;
    },
    (error) => Promise.reject(error)
  );

  // 响应拦截器：处理 401 错误和 token 刷新
  api.interceptors.response.use(
    (response) => response.data,
    async (error) => {
      const originalRequest = error.config;
      
      // 不处理认证相关端点的错误
      const isAuthEndpoint = [
        '/v1/auth/login',
        '/v1/auth/register',
        '/v1/auth/refresh',
        '/v1/auth/logout',
        '/v1/auth/forgot-password',
        '/v1/auth/verify-reset-token',
        '/v1/auth/reset-password'
      ].some(endpoint => originalRequest.url?.includes(endpoint));
      
      if (isAuthEndpoint) {
        return Promise.reject(error);
      }
      
      // 处理 401 错误
      if (error.response?.status === 401 && !originalRequest._retry) {
        
        // 如果正在刷新 token，将请求加入队列
        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          }).then(() => {
            return api(originalRequest);
          }).catch((err) => {
            return Promise.reject(err);
          });
        }
        
        originalRequest._retry = true;
        
        // 检查是否有 refresh token
        if (!authManager.hasRefreshToken()) {
          authManager.clearAuth();
          uiManager.showTokenExpiryDialog();
          return Promise.reject(error);
        }
        
        isRefreshing = true;
        
        try {
          // 刷新 token
          await authManager.refreshToken();
          processQueue(null);
          
          // 重试原请求
          return api(originalRequest);
          
        } catch (refreshError) {
          // 刷新失败，清理状态
          processQueue(refreshError);
          authManager.clearAuth();
          uiManager.showTokenExpiryDialog();
          return Promise.reject(refreshError);
          
        } finally {
          isRefreshing = false;
        }
      }
      
      return Promise.reject(error);
    }
  );
}
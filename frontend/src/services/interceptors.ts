import { AxiosInstance } from 'axios';
import { authManager } from './authManager';
import { uiManager } from './uiManager';
import { TokenResponse } from '../types/auth';

/**
 * Interface for failed request queue items
 */
interface FailedRequest {
  resolve: (value?: unknown) => void;
  reject: (error?: unknown) => void;
}

/**
 * JWT Token Utilities
 */

/**
 * Check if a JWT token has expired
 * @param {string} token - JWT access token
 * @returns {boolean} True if token is expired or invalid
 */
const isTokenExpired = (token: string): boolean => {
  if (!token) return true;
  try {
    // Validate JWT format (should have 3 parts separated by dots)
    const parts = token.split('.');
    if (parts.length !== 3) return true;
    
    // Decode the payload (middle part of JWT)
    const payload = JSON.parse(atob(parts[1]));
    if (!payload.exp) return true;
    
    // Check if token has expired (exp is in seconds, Date.now() is in milliseconds)
    return payload.exp * 1000 <= Date.now();
  } catch {
    // If any parsing fails, consider token invalid
    return true;
  }
};

/**
 * Extract expiration time from a JWT token
 * @param {string} token - JWT access token
 * @returns {number | null} Expiration timestamp in milliseconds, or null if invalid
 */
const getTokenExpiryTime = (token: string): number | null => {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    
    const payload = JSON.parse(atob(parts[1]));
    return payload.exp ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
};

/**
 * Interceptor Manager Class
 * Encapsulates all axios interceptor logic and state management
 */
class InterceptorManager {
  private refreshPromise: Promise<TokenResponse> | null = null;
  private failedQueue: FailedRequest[] = [];

  /**
   * Process all queued requests after token refresh completes
   * @param {Error | null} error - Refresh error, if any
   * @param {string | null} token - New access token, if successful
   */
  private processQueue(error: Error | null, token: string | null = null): void {
    this.failedQueue.forEach(({ resolve, reject }) => {
      if (error) {
        reject(error);
      } else {
        resolve(token);
      }
    });
    
    // Clear the queue after processing
    this.failedQueue = [];
  }

  /**
   * Setup request interceptor
   * Handles automatic token addition and proactive refresh
   */
  setupRequestInterceptor(api: AxiosInstance): void {
    api.interceptors.request.use(
      async (config) => {
        // Define endpoints that don't require authentication
        const publicEndpoints = ['/v1/auth/login', '/v1/auth/register', '/v1/auth/refresh'];
        const isPublicEndpoint = publicEndpoints.some(endpoint => config.url?.includes(endpoint));
        
        // Only add auth headers for protected endpoints
        if (!isPublicEndpoint) {
          const accessToken = authManager.getAccessToken();
          
          if (accessToken) {
            // Simply add the current access token to request headers
            // Let the response interceptor handle token refresh if needed
            config.headers.Authorization = `Bearer ${accessToken}`;
          }
        }
        return config;
      },
      (error) => Promise.reject(error)
    );
  }

  /**
   * Setup response interceptor
   * Handles 401 errors by attempting token refresh and retrying failed requests
   */
  setupResponseInterceptor(api: AxiosInstance): void {
    api.interceptors.response.use(
      // Success response handler - just return the data
      (response) => response.data,
      
      // Error response handler
      async (error) => {
        const originalRequest = error.config;

        // Don't attempt token refresh for authentication endpoints
        const isAuthRequest = originalRequest.url?.includes('/v1/auth/login') || 
                             originalRequest.url?.includes('/v1/auth/register') ||
                             originalRequest.url?.includes('/v1/auth/refresh') ||
                             originalRequest.url?.includes('/v1/auth/logout');
        
        // Handle 401 Unauthorized errors for protected endpoints
        if (error.response?.status === 401 && !originalRequest._retry && !isAuthRequest) {
          // If a refresh is already in progress, queue this request
          if (this.refreshPromise) {
            return new Promise((resolve, reject) => {
              this.failedQueue.push({ resolve, reject });
            }).then(() => {
              // Retry the original request with new token
              return api(originalRequest);
            }).catch((err: Error) => {
              return Promise.reject(err);
            });
          }

          // Mark this request as retried to prevent infinite loops
          originalRequest._retry = true;

          try {
            if (authManager.hasRefreshToken()) {
              // Start token refresh process
              this.refreshPromise = authManager.refreshToken();
              await this.refreshPromise;
              this.refreshPromise = null;
              
              // Process all queued requests with success
              this.processQueue(null);
              
              // Retry the original request with new token
              return api(originalRequest);
            } else {
              throw new Error('No refresh token available');
            }
          } catch (refreshError) {
            // Token refresh failed - handle cleanup and user notification
            this.refreshPromise = null;
            this.processQueue(refreshError as Error);
            
            // Clear authentication state
            authManager.clearAuth();
            
            // Show user-friendly token expiry dialog
            uiManager.showTokenExpiryDialog();
            
            return Promise.reject(refreshError);
          }
        }

        // Log all API errors for debugging
        console.error('API Error:', error);
        return Promise.reject(error);
      }
    );
  }
}

// Create singleton instance
const interceptorManager = new InterceptorManager();

/**
 * Setup all interceptors for the given axios instance
 * @param {AxiosInstance} api - Axios instance to configure
 */
export function setupInterceptors(api: AxiosInstance): void {
  interceptorManager.setupRequestInterceptor(api);
  interceptorManager.setupResponseInterceptor(api);
}

// Export utility functions for potential external use
export { isTokenExpired, getTokenExpiryTime };
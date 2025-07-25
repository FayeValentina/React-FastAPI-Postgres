import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import api from '../services/api';
import { 
  LoginRequest, 
  RegisterRequest, 
  TokenResponse, 
  User, 
  AuthState 
} from '../types/auth';
import { extractAuthErrorMessage } from '../utils/errorHandler';
import { useUIStore } from './ui-store';

interface AuthStore extends AuthState {
  // Actions
  login: (credentials: LoginRequest) => Promise<TokenResponse>;
  register: (userData: RegisterRequest) => Promise<User>;
  logout: (skipServerRequest?: boolean) => Promise<void>;
  getCurrentUser: () => Promise<User>;
  refreshAccessToken: () => Promise<TokenResponse>;
  clearError: () => void;
  setLoading: (loading: boolean) => void;
}

export const useAuthStore = create<AuthStore>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        user: null,
        accessToken: null,
        refreshToken: null,
        isAuthenticated: false,
        loading: false,
        error: null,

        // Actions
        login: async (credentials: LoginRequest) => {
          set({ loading: true, error: null });
          
          try {
            const tokenData = await api.post('/v1/auth/login', credentials) as TokenResponse;
            
            // 设置token后立即获取用户信息
            set({
              accessToken: tokenData.access_token,
              refreshToken: tokenData.refresh_token || null,
              isAuthenticated: true,
              error: null,
            });

            // 设置Authorization header并获取用户信息
            api.defaults.headers.common['Authorization'] = `Bearer ${tokenData.access_token}`;
            const user = await api.get('/v1/auth/me') as User;
            
            set({ 
              user,
              loading: false,
            });

            return tokenData;
          } catch (error: any) {
            const errorMessage = extractAuthErrorMessage(error);
            
            set({
              loading: false,
              error: errorMessage,
              isAuthenticated: false,
              accessToken: null,
              refreshToken: null,
              user: null,
            });
            throw error;
          }
        },

        register: async (userData: RegisterRequest) => {
          set({ loading: true, error: null });
          
          try {
            // Clean userData to remove undefined values that might cause issues
            const cleanedData = {
              email: userData.email,
              username: userData.username,
              password: userData.password,
              ...(userData.full_name && { full_name: userData.full_name }),
              ...(userData.age !== undefined && userData.age !== null && { age: userData.age }),
            };
            
            const user = await api.post('/v1/auth/register', cleanedData) as User;
            
            set({ loading: false, error: null });
            return user;
          } catch (error: any) {
            const errorMessage = extractAuthErrorMessage(error);
            
            set({ loading: false, error: errorMessage });
            throw error;
          }
        },

        logout: async (skipServerRequest = false) => {
          const { accessToken, isAuthenticated } = get();
          
          // Only attempt server logout if we have a valid token and are authenticated
          if (!skipServerRequest && accessToken && isAuthenticated) {
            try {
              // Request interceptor will automatically add Authorization header
              await api.post('/v1/auth/logout');
            } catch (error: any) {
              console.error('Logout request failed:', error);
              // Continue with logout even if server request fails
              // Don't trigger token refresh on logout failure
              if (error.response?.status === 401) {
                console.log('Token already expired, proceeding with local logout');
              }
            }
          }

          // Always clear auth state and headers regardless of server response
          delete api.defaults.headers.common['Authorization'];
          set({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
            loading: false,
            error: null,
          });
        },

        getCurrentUser: async () => {
          const { accessToken } = get();
          
          if (!accessToken) {
            throw new Error('No access token available');
          }

          try {
            // Set authorization header
            api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;
            const user = await api.get('/v1/auth/me') as User;
            
            set({ user });
            return user;
          } catch (error) {
            // If token is invalid, clear auth state
            set({
              user: null,
              accessToken: null,
              refreshToken: null,
              isAuthenticated: false,
            });
            delete api.defaults.headers.common['Authorization'];
            throw error;
          }
        },

        refreshAccessToken: async () => {
          const { refreshToken: currentRefreshToken } = get();
          
          if (!currentRefreshToken) {
            throw new Error('No refresh token available');
          }

          try {
            const tokenData = await api.post('/v1/auth/refresh', {
              refresh_token: currentRefreshToken,
            }) as TokenResponse;
            
            set({
              accessToken: tokenData.access_token,
              refreshToken: tokenData.refresh_token || currentRefreshToken,
              isAuthenticated: true,
            });

            return tokenData;
          } catch (error) {
            // If refresh fails, clear auth state and ensure loading is false
            set({
              user: null,
              accessToken: null,
              refreshToken: null,
              isAuthenticated: false,
              loading: false,
            });
            delete api.defaults.headers.common['Authorization'];
            throw error;
          }
        },

        clearError: () => {
          set({ error: null });
        },

        setLoading: (loading: boolean) => {
          set({ loading });
        },
      }),
      {
        name: 'auth-store',
        partialize: (state) => ({
          user: state.user,
          accessToken: state.accessToken,
          refreshToken: state.refreshToken,
          isAuthenticated: state.isAuthenticated,
        }),
      }
    ),
    {
      name: 'auth-store',
    }
  )
);

// Setup axios interceptor for automatic token refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (error?: unknown) => void;
}> = [];

const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token);
    }
  });
  
  failedQueue = [];
};

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const state = useAuthStore.getState();
    
    // Don't add auth header for login, register, and refresh requests
    // logout and /me endpoints DO need auth headers
    const publicEndpoints = ['/v1/auth/login', '/v1/auth/register', '/v1/auth/refresh'];
    const isPublicEndpoint = publicEndpoints.some(endpoint => config.url?.includes(endpoint));
    
    if (state.accessToken && !isPublicEndpoint) {
      config.headers.Authorization = `Bearer ${state.accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const originalRequest = error.config;

    // Don't try to refresh tokens for auth-related requests
    const isAuthRequest = originalRequest.url?.includes('/v1/auth/login') || 
                         originalRequest.url?.includes('/v1/auth/register') ||
                         originalRequest.url?.includes('/v1/auth/refresh') ||
                         originalRequest.url?.includes('/v1/auth/logout');
    
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthRequest) {
      // If already refreshing, queue the request
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => {
          return api(originalRequest);
        }).catch((err: Error) => {
          return Promise.reject(err);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const state = useAuthStore.getState();

      try {
        if (state.refreshToken) {
          // Try to refresh the token
          await state.refreshAccessToken();
          processQueue(null);
          return api(originalRequest);
        } else {
          // No refresh token available
          throw new Error('No refresh token available');
        }
      } catch (refreshError) {
        // Token refresh failed, handle logout and redirect
        processQueue(refreshError as Error);
        
        // Immediate cleanup without server requests
        state.setLoading(false);
        delete api.defaults.headers.common['Authorization'];
        
        // Clear auth state synchronously (avoiding server logout request)
        useAuthStore.setState({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
          loading: false,
          error: null,
        });
        
        // Show token expiry dialog instead of direct redirect
        useUIStore.getState().showTokenExpiryDialog();
        
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    console.error('API Error:', error);
    return Promise.reject(error);
  }
);
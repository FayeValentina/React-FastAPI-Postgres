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
  // Internal helper
  clearAuthState: () => void;
  isTokenValid: () => boolean;
  getTokenTimeRemaining: () => number;
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
        lastUserFetch: null, //上次获取用户信息的时间

        // Internal helper for clearing auth state
        clearAuthState: () => {
          set({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
            loading: false,
            error: null,
            lastUserFetch: null,
          });
          delete api.defaults.headers.common['Authorization'];
        },

        isTokenValid: () => {
            const { accessToken } = get();
            return accessToken && !isTokenExpired(accessToken);
        },

        getTokenTimeRemaining: () => {
            const { accessToken } = get();
            if (!accessToken) return 0;
            const expiry = getTokenExpiryTime(accessToken);
            return expiry ? Math.max(0, expiry - Date.now()) : 0;
        },
        // Actions
        login: async (credentials: LoginRequest) => {
          set({ loading: true, error: null });
          
          try {
            const tokenData = await api.post('/v1/auth/login', credentials) as TokenResponse;
            
            // 先设置token状态，让interceptor自动处理header
            set({
              accessToken: tokenData.access_token,
              refreshToken: tokenData.refresh_token || null,
              isAuthenticated: true,
              error: null,
            });

            // 然后获取用户信息
            const user = await api.get('/v1/auth/me') as User;
            set({ user, loading: false });

            return tokenData;
          } catch (error: any) {
            const errorMessage = extractAuthErrorMessage(error);
            
            get().clearAuthState();
            set({ loading: false, error: errorMessage });
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
          get().clearAuthState();
        },

        getCurrentUser: async () => {
          const { accessToken, user: cachedUser, lastUserFetch } = get();
          
          if (!accessToken) {
            throw new Error('No access token available');
          }

          // Return cached user if available and valid
          if (cachedUser && lastUserFetch && Date.now() - lastUserFetch < 5 * 60 * 1000) {
            return cachedUser;
          }

          try {
            // interceptor will automatically add Authorization header
            const user = await api.get('/v1/auth/me') as User;
            
            set({ 
              user,
              lastUserFetch: Date.now() // 记录获取时间
            });
            return user;
          } catch (error) {
            // If token is invalid, clear auth state
            get().clearAuthState();
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
            // If refresh fails, clear auth state
            get().clearAuthState();
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
          lastUserFetch: state.lastUserFetch,
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
let refreshPromise: Promise<TokenResponse> | null = null;
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

const isTokenExpired = (token: string): boolean => {
  if (!token) return true;
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
};

const getTokenExpiryTime = (token: string): number | null => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000;
  } catch {
    return null;
  }
};

// Request interceptor改进版本
api.interceptors.request.use(
  async (config) => {
    const state = useAuthStore.getState();
    const publicEndpoints = ['/v1/auth/login', '/v1/auth/register', '/v1/auth/refresh'];
    const isPublicEndpoint = publicEndpoints.some(endpoint => config.url?.includes(endpoint));
    
    if (!isPublicEndpoint && state.accessToken) {
      // 检查token是否即将过期（提前5分钟刷新）
      const timeRemaining = state.getTokenTimeRemaining();
      if (timeRemaining > 0 && timeRemaining < 5 * 60 * 1000 && state.refreshToken && !isRefreshing) {
        try {
          console.log('Token expiring soon, refreshing...');
          if (!refreshPromise) {
            refreshPromise = state.refreshAccessToken();
          }
          await refreshPromise;
          refreshPromise = null;
        } catch (error) {
          console.error('Proactive token refresh failed:', error);
          refreshPromise = null;
          // 让后续的response interceptor处理
        }
      }
      
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
          // Use shared refresh promise to avoid multiple concurrent refresh requests
          if (!refreshPromise) {
            refreshPromise = state.refreshAccessToken();
          }
          await refreshPromise;
          refreshPromise = null;
          processQueue(null);
          return api(originalRequest);
        } else {
          // No refresh token available
          throw new Error('No refresh token available');
        }
      } catch (refreshError) {
        refreshPromise = null;
        // Token refresh failed, handle logout and redirect
        processQueue(refreshError as Error);
        
        // Immediate cleanup without server requests
        state.setLoading(false);
        delete api.defaults.headers.common['Authorization'];
        
        // Clear auth state synchronously (avoiding server logout request)
        state.clearAuthState();
        
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
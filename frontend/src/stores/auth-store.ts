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

interface AuthStore extends AuthState {
  // Actions
  login: (credentials: LoginRequest) => Promise<TokenResponse>;
  register: (userData: RegisterRequest) => Promise<User>;
  logout: () => Promise<void>;
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
            const tokenData = await api.post('/api/v1/auth/login', credentials) as TokenResponse;
            
            set({
              accessToken: tokenData.access_token,
              refreshToken: tokenData.refresh_token || null,
              isAuthenticated: true,
              loading: false,
              error: null,
            });

            // Get user info after login
            try {
              const user = await get().getCurrentUser();
              set({ user });
            } catch (error) {
              console.error('Failed to get user info after login:', error);
            }

            return tokenData;
          } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Login failed';
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
            const user = await api.post('/api/v1/auth/register', userData) as User;
            
            set({ loading: false, error: null });
            return user;
          } catch (error) {
            const errorMessage = error instanceof Error ? error.message : 'Registration failed';
            set({ loading: false, error: errorMessage });
            throw error;
          }
        },

        logout: async () => {
          const { accessToken } = get();
          
          if (accessToken) {
            try {
              // Set authorization header for logout request
              api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;
              await api.post('/api/v1/auth/logout');
            } catch (error) {
              console.error('Logout request failed:', error);
            } finally {
              // Clear authorization header
              delete api.defaults.headers.common['Authorization'];
            }
          }

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
            const user = await api.get('/api/v1/auth/me') as User;
            
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
            const tokenData = await api.post('/api/v1/auth/refresh', {
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
    if (state.accessToken && state.isAuthenticated) {
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

    if (error.response?.status === 401 && !originalRequest._retry) {
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

      if (state.refreshToken) {
        try {
          await state.refreshAccessToken();
          processQueue(null);
          return api(originalRequest);
        } catch (refreshError) {
          processQueue(refreshError as Error);
          state.logout();
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      } else {
        state.logout();
      }
    }

    console.error('API Error:', error);
    return Promise.reject(error);
  }
);
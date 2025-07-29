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

/**
 * Extended AuthStore interface that includes both state and actions
 * Combines the base AuthState with methods for authentication operations
 */
interface AuthStore extends AuthState {
  // Core authentication actions
  login: (credentials: LoginRequest) => Promise<TokenResponse>;
  register: (userData: RegisterRequest) => Promise<User>;
  logout: (skipServerRequest?: boolean) => Promise<void>;
  getCurrentUser: () => Promise<User>;
  refreshAccessToken: () => Promise<TokenResponse>;
  
  // UI and error management
  clearError: () => void;
  setLoading: (loading: boolean) => void;
  
  // Internal state management helpers
  clearAuthState: () => void;
  isTokenValid: () => boolean;
  getTokenTimeRemaining: () => number;
}

/**
 * Main authentication store using Zustand with persistence and devtools
 * Manages user authentication state, tokens, and related operations
 */
export const useAuthStore = create<AuthStore>()(
  devtools(
    persist(
      (set, get) => ({
        // ==================== INITIAL STATE ====================
        user: null,                    // Current authenticated user object
        accessToken: null,             // JWT access token for API requests
        refreshToken: null,            // JWT refresh token for token renewal
        isAuthenticated: false,        // Boolean flag for authentication status
        loading: false,                // Loading state for async operations
        error: null,                   // Current error message, if any
        lastUserFetch: null,           // Timestamp of last user data fetch (for caching)

        // ==================== INTERNAL HELPERS ====================
        
        /**
         * Comprehensive state cleanup function
         * Resets all authentication-related state and removes API headers
         * Used during logout, token refresh failures, and authentication errors
         */
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
          // Remove Authorization header from all future API requests
          delete api.defaults.headers.common['Authorization'];
        },

        /**
         * Validates if the current access token is still valid
         * Checks both token existence and expiration status
         * @returns {boolean} True if token exists and hasn't expired
         */
        isTokenValid: () => {
          const { accessToken } = get();
          return accessToken && !isTokenExpired(accessToken);
        },

        /**
         * Calculates remaining time before token expires
         * Used for proactive token refresh decisions
         * @returns {number} Milliseconds until token expiration (0 if invalid/expired)
         */
        getTokenTimeRemaining: () => {
          const { accessToken } = get();
          if (!accessToken) return 0;
          const expiry = getTokenExpiryTime(accessToken);
          return expiry ? Math.max(0, expiry - Date.now()) : 0;
        },

        // ==================== AUTHENTICATION ACTIONS ====================

        /**
         * User login with credentials
         * Handles token storage, user data fetching, and error management
         * @param {LoginRequest} credentials - User login credentials (email/username + password)
         * @returns {Promise<TokenResponse>} Token data from server
         */
        login: async (credentials: LoginRequest) => {
          // Set loading state and clear any previous errors
          set({ loading: true, error: null });
          
          try {
            // Send login request to server
            const tokenData = await api.post('/v1/auth/login', credentials) as TokenResponse;
            
            // Fix: Atomically set all token-related state to prevent race conditions
            // Issue: Multiple set() calls could create intermediate states where interceptors might execute
            set({
              accessToken: tokenData.access_token,
              refreshToken: tokenData.refresh_token || null,
              isAuthenticated: true,
              error: null,
            });

            // Fetch user profile data using the new access token
            // The request interceptor will automatically add the Authorization header
            const user = await api.get('/v1/auth/me') as User;
            
            // Fix: Atomically update user data and loading state for consistent UI
            // Issue: Separate updates could cause UI inconsistencies during state transitions
            set({ 
              user, 
              loading: false,
              lastUserFetch: Date.now()  // Cache timestamp for future reference
            });

            return tokenData;
          } catch (error: any) {
            const errorMessage = extractAuthErrorMessage(error);
            
            // Fix: Ensure complete state cleanup on authentication failure
            // Issue: Partial state cleanup could leave the app in an inconsistent state
            get().clearAuthState();
            set({ loading: false, error: errorMessage });
            throw error;
          }
        },

        /**
         * User registration with form data
         * Cleans input data and handles registration errors
         * @param {RegisterRequest} userData - User registration data
         * @returns {Promise<User>} Created user object
         */
        register: async (userData: RegisterRequest) => {
          set({ loading: true, error: null });
          
          try {
            // Clean userData to remove undefined/null values that might cause server issues
            // Only include fields that have actual values
            const cleanedData = {
              email: userData.email,
              username: userData.username,
              password: userData.password,
              // Conditionally include optional fields only if they have values
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

        /**
         * User logout with optional server notification
         * Handles both server-side and client-side cleanup
         * @param {boolean} skipServerRequest - If true, only clears local state
         */
        logout: async (skipServerRequest = false) => {
          const { accessToken, isAuthenticated } = get();
          
          // Only attempt server logout if we have valid credentials
          // This prevents unnecessary server requests when already logged out
          if (!skipServerRequest && accessToken && isAuthenticated) {
            try {
              // The request interceptor will automatically add Authorization header
              await api.post('/v1/auth/logout');
            } catch (error: any) {
              console.error('Logout request failed:', error);
              // Continue with logout even if server request fails
              // This ensures user can always log out locally
              if (error.response?.status === 401) {
                console.log('Token already expired, proceeding with local logout');
              }
            }
          }

          // Always clear local auth state regardless of server response
          // This ensures a clean slate for the next user session
          get().clearAuthState();
        },

        /**
         * Fetches current user data with intelligent caching
         * Implements caching strategy to reduce unnecessary API calls
         * @returns {Promise<User>} Current user data
         */
        getCurrentUser: async () => {
          const { accessToken, user: cachedUser, lastUserFetch } = get();
          
          if (!accessToken) {
            throw new Error('No access token available');
          }

          // Fix: Validate both token validity and cache freshness
          // Issue: Original code only checked cache time, ignoring token expiration
          const isTokenStillValid = get().isTokenValid();
          const isCacheValid = cachedUser && 
            lastUserFetch && 
            Date.now() - lastUserFetch < 5 * 60 * 1000;  // 5-minute cache window

          // Only return cached data if both token and cache are valid
          // This prevents returning stale data with an expired token
          if (isTokenStillValid && isCacheValid) {
            return cachedUser;
          }

          try {
            // Fetch fresh user data from server
            const user = await api.get('/v1/auth/me') as User;
            
            // Update cache with fresh data and timestamp
            set({ 
              user,
              lastUserFetch: Date.now()
            });
            return user;
          } catch (error) {
            // Fix: Only clear state on confirmed authentication errors
            // Issue: Any error would log out user, including network issues
            if ((error as any)?.response?.status === 401) {
              get().clearAuthState();
            }
            throw error;
          }
        },

        /**
         * Refreshes the access token using the refresh token
         * Handles token renewal and state updates
         * @returns {Promise<TokenResponse>} New token data
         */
        refreshAccessToken: async () => {
          const { refreshToken: currentRefreshToken } = get();
          
          if (!currentRefreshToken) {
            throw new Error('No refresh token available');
          }

          try {
            // Request new access token from server
            const tokenData = await api.post('/v1/auth/refresh', {
              refresh_token: currentRefreshToken,
            }) as TokenResponse;
            
            // Update stored tokens with new values
            // Use new refresh token if provided, otherwise keep current one
            set({
              accessToken: tokenData.access_token,
              refreshToken: tokenData.refresh_token || currentRefreshToken,
              isAuthenticated: true,
            });

            return tokenData;
          } catch (error) {
            // If refresh fails, user needs to log in again
            get().clearAuthState();
            throw error;
          }
        },

        // ==================== UI STATE MANAGEMENT ====================

        /**
         * Clears the current error message
         * Used for dismissing error notifications
         */
        clearError: () => {
          set({ error: null });
        },

        /**
         * Manually sets the loading state
         * Used for external loading control
         * @param {boolean} loading - New loading state
         */
        setLoading: (loading: boolean) => {
          set({ loading });
        },
      }),
      {
        // Zustand persistence configuration
        name: 'auth-store',
        // Only persist essential auth data, exclude UI state like loading/error
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
      // Redux DevTools configuration
      name: 'auth-store',
    }
  )
);

// ==================== TOKEN REFRESH COORDINATION ====================

/**
 * Global state for managing concurrent token refresh operations
 * Prevents multiple simultaneous refresh requests that could cause race conditions
 */
// Fix: Simplified and unified refresh state management using only refreshPromise
let refreshPromise: Promise<TokenResponse> | null = null;

/**
 * Queue for requests that need to wait for token refresh completion
 * Stores resolve/reject functions to be called after refresh completes
 */
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (error?: unknown) => void;
}> = [];

/**
 * Processes all queued requests after token refresh completes
 * Either resolves them with the new token or rejects them with the error
 * @param {Error | null} error - Refresh error, if any
 * @param {string | null} token - New access token, if successful
 */
const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token);
    }
  });
  
  // Clear the queue after processing
  failedQueue = [];
};

// ==================== JWT TOKEN UTILITIES ====================

/**
 * Fix: Enhanced JWT token expiration checking with format validation
 * Safely checks if a JWT token has expired
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
 * Extracts the expiration time from a JWT token
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

// ==================== AXIOS INTERCEPTORS ====================

/**
 * Fix: Enhanced request interceptor with proactive token refresh
 * Automatically adds Authorization headers and handles proactive token refresh
 */
api.interceptors.request.use(
  async (config) => {
    const state = useAuthStore.getState();
    
    // Define endpoints that don't require authentication
    const publicEndpoints = ['/v1/auth/login', '/v1/auth/register', '/v1/auth/refresh'];
    const isPublicEndpoint = publicEndpoints.some(endpoint => config.url?.includes(endpoint));
    
    // Only add auth headers for protected endpoints
    if (!isPublicEndpoint && state.accessToken) {
      // Fix: More accurate token expiration checking for proactive refresh
      const timeRemaining = state.getTokenTimeRemaining();
      
      // Proactively refresh token if it expires within 5 minutes
      // This prevents requests from failing due to token expiration
      const shouldRefresh = timeRemaining > 0 && 
                           timeRemaining < 5 * 60 * 1000 && 
                           state.refreshToken && 
                           !refreshPromise; // Prevent multiple concurrent refreshes
      
      if (shouldRefresh) {
        try {
          console.log('Token expiring soon, refreshing...');
          refreshPromise = state.refreshAccessToken();
          await refreshPromise;
          refreshPromise = null;
        } catch (error) {
          console.error('Proactive token refresh failed:', error);
          refreshPromise = null;
          // Let the response interceptor handle the failure
        }
      }
      
      // Add current access token to request headers
      config.headers.Authorization = `Bearer ${state.accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/**
 * Fix: Enhanced response interceptor with better error handling and queue management
 * Handles 401 errors by attempting token refresh and retrying failed requests
 */
api.interceptors.response.use(
  // Success response handler - just return the data
  (response) => response.data,
  
  // Error response handler
  async (error) => {
    const originalRequest = error.config;

    // Don't attempt token refresh for authentication endpoints
    // This prevents infinite loops when auth endpoints themselves fail
    const isAuthRequest = originalRequest.url?.includes('/v1/auth/login') || 
                         originalRequest.url?.includes('/v1/auth/register') ||
                         originalRequest.url?.includes('/v1/auth/refresh') ||
                         originalRequest.url?.includes('/v1/auth/logout');
    
    // Handle 401 Unauthorized errors for protected endpoints
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthRequest) {
      // Fix: Unified refresh state management using refreshPromise
      
      // If a refresh is already in progress, queue this request
      if (refreshPromise) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => {
          // Retry the original request with new token
          return api(originalRequest);
        }).catch((err: Error) => {
          return Promise.reject(err);
        });
      }

      // Mark this request as retried to prevent infinite loops
      originalRequest._retry = true;
      const state = useAuthStore.getState();

      try {
        if (state.refreshToken) {
          // Start token refresh process
          refreshPromise = state.refreshAccessToken();
          await refreshPromise;
          refreshPromise = null;
          
          // Process all queued requests with success
          processQueue(null);
          
          // Retry the original request with new token
          return api(originalRequest);
        } else {
          throw new Error('No refresh token available');
        }
      } catch (refreshError) {
        // Token refresh failed - handle cleanup and user notification
        refreshPromise = null;
        processQueue(refreshError as Error);
        
        // Clear authentication state
        state.clearAuthState();
        
        // Show user-friendly token expiry dialog instead of abrupt redirect
        useUIStore.getState().showTokenExpiryDialog();
        
        return Promise.reject(refreshError);
      }
    }

    // Log all API errors for debugging
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

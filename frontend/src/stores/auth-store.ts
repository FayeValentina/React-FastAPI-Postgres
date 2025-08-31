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
import { extractAuthErrorMessage, type ApiError } from '../utils/errorHandler';

// ==================== JWT TOKEN UTILITIES ====================

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
        },

        /**
         * Validates if the current access token is still valid
         * Checks both token existence and expiration status
         * @returns {boolean} True if token exists and hasn't expired
         */
        isTokenValid: () => {
          const { accessToken } = get();
          return !!accessToken && !isTokenExpired(accessToken);
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
          } catch (error: unknown) {
            const errorMessage = extractAuthErrorMessage(error as ApiError);
            
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
          set({ error: null });
          
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
            
            return user;
          } catch (error: unknown) {
            const errorMessage = extractAuthErrorMessage(error as ApiError);
            
            set({ error: errorMessage });
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
            } catch (error: unknown) {
              console.error('Logout request failed:', error);
              // Continue with logout even if server request fails
              // This ensures user can always log out locally
              if ((error as ApiError).response?.status === 401) {
                console.log('Token already expired, proceeding with local logout');
              }
            }
          }

          // Always clear local auth state regardless of server response
          // This ensures a clean slate for the next user session
          get().clearAuthState();
        },

        /**
         * Fetches current user data from server
         * Always fetches fresh data to ensure consistency after updates
         * @returns {Promise<User>} Current user data
         */
        getCurrentUser: async () => {
          const { accessToken } = get();
          
          if (!accessToken) {
            throw new Error('No access token available');
          }

          try {
            // Always fetch fresh user data from server
            const user = await api.get('/v1/auth/me') as User;
            
            // Update stored user data
            set({ 
              user,
              lastUserFetch: Date.now()
            });
            return user;
          } catch (error) {
            // Only clear state on confirmed authentication errors
            if ((error as { response?: { status?: number } })?.response?.status === 401) {
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


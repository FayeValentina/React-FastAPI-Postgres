import { useAuthStore } from '../stores/auth-store';
import { TokenResponse } from '../types/auth';

/**
 * Authentication Manager
 * Provides a clean interface for authentication operations
 * Simplified to work with the new interceptor implementation
 */
class AuthManager {
  /**
   * Get the current access token
   * @returns {string | null} Current access token or null if not available
   */
  getAccessToken(): string | null {
    return useAuthStore.getState().accessToken;
  }

  /**
   * Check if a refresh token is available
   * @returns {boolean} True if refresh token exists
   */
  hasRefreshToken(): boolean {
    return !!useAuthStore.getState().refreshToken;
  }

  /**
   * Execute token refresh operation
   * @returns {Promise<TokenResponse>} New token data
   */
  async refreshToken(): Promise<TokenResponse> {
    return useAuthStore.getState().refreshAccessToken();
  }

  /**
   * Clear all authentication state
   */
  clearAuth(): void {
    useAuthStore.getState().clearAuthState();
  }
}

// Export singleton instance
export const authManager = new AuthManager();
import { useAuthStore } from '../stores/auth-store';
import { TokenResponse } from '../types/auth';

/**
 * Authentication Manager
 * Provides a clean interface for authentication operations
 * Separates auth logic from store implementation details
 */
export class AuthManager {
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
   * Determine if token should be refreshed
   * Checks if we have a refresh token and current token is expired or expiring soon
   * @returns {boolean} True if token should be refreshed
   */
  shouldRefreshToken(): boolean {
    const state = useAuthStore.getState();
    if (!state.refreshToken || !state.accessToken) return false;
    
    const timeRemaining = state.getTokenTimeRemaining();
    
    // Only refresh if token is expired or expiring very soon (less than 1 minute)
    return timeRemaining <= 1 * 60 * 1000;
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

  /**
   * Check if current token is valid
   * @returns {boolean} True if token is valid and not expired
   */
  isTokenValid(): boolean {
    return useAuthStore.getState().isTokenValid();
  }

  /**
   * Get remaining time before token expires
   * @returns {number} Milliseconds until expiration (0 if invalid)
   */
  getTokenTimeRemaining(): number {
    return useAuthStore.getState().getTokenTimeRemaining();
  }
}

// Export singleton instance
export const authManager = new AuthManager();
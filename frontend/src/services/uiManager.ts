import { useUIStore } from '../stores/ui-store';

/**
 * UI Manager
 * Handles UI interactions related to authentication
 * Provides a clean interface for UI operations
 */
export class UIManager {
  /**
   * Show token expiry dialog to user
   * Called when token refresh fails and user needs to re-authenticate
   */
  showTokenExpiryDialog(): void {
    useUIStore.getState().showTokenExpiryDialog();
  }
}

// Export singleton instance
export const uiManager = new UIManager();
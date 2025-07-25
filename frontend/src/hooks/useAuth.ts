import { useCallback } from 'react';
import { useAuthStore } from '../stores/auth-store';
import { LoginRequest, RegisterRequest } from '../types/auth';

export const useAuth = () => {
  const authStore = useAuthStore();

  const login = useCallback(async (credentials: LoginRequest) => {
    await authStore.login(credentials);
    if (authStore.isAuthenticated) {
      await authStore.getCurrentUser();
    }
  }, [authStore]);

  const register = useCallback(async (userData: RegisterRequest) => {
    return await authStore.register(userData);
  }, [authStore]);

  const logout = useCallback(async () => {
    await authStore.logout();
  }, [authStore]);

  return {
    user: authStore.user,
    isAuthenticated: authStore.isAuthenticated,
    loading: authStore.loading,
    error: authStore.error,
    login,
    register,
    logout,
    clearError: authStore.clearError,
  };
};
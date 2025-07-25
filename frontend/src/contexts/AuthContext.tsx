import React, { createContext, useContext, useEffect, ReactNode } from 'react';
import { useAuthStore } from '../stores/auth-store';
import { LoginRequest, RegisterRequest, User } from '../types/auth';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  register: (userData: RegisterRequest) => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const authStore = useAuthStore();

  // 应用启动时初始化认证状态
  useEffect(() => {
    const initAuth = async () => {
      if (authStore.accessToken && !authStore.user) {
        try {
          await authStore.getCurrentUser();
        } catch (error) {
          console.error('Token validation failed:', error);
          authStore.logout();
        }
      }
    };

    initAuth();
  }, []);

  const contextValue: AuthContextType = {
    user: authStore.user,
    isAuthenticated: authStore.isAuthenticated,
    loading: authStore.loading,
    error: authStore.error,
    login: async (credentials) => {
      await authStore.login(credentials);
      if (authStore.isAuthenticated) {
        await authStore.getCurrentUser();
      }
    },
    logout: authStore.logout,
    register: authStore.register,
    clearError: authStore.clearError,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
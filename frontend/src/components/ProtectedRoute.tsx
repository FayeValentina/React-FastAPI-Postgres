import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { CircularProgress, Box, Typography } from '@mui/material';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAuth?: boolean;
  requiredRoles?: string[];
  fallback?: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requireAuth = true,
  requiredRoles = [],
  fallback
}) => {
  const { isAuthenticated, loading, user } = useAuth();
  const location = useLocation();

  // 显示加载状态
  if (loading) {
    return fallback || (
      <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
        <Typography variant="h6" sx={{ mt: 2 }}>
          正在验证身份...
        </Typography>
      </Box>
    );
  }

  // 需要认证但未登录
  if (requireAuth && !isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 不需要认证但已登录（登录页、注册页）
  if (!requireAuth && isAuthenticated) {
    const from = location.state?.from?.pathname || '/dashboard';
    return <Navigate to={from} replace />;
  }

  // 角色权限检查
  if (requireAuth && requiredRoles.length > 0) {
    const hasRequiredRole = requiredRoles.some(role => {
      // 检查用户是否有特定角色或者是超级用户
      if (user?.is_superuser) return true;
      // 注意：当前User类型没有roles字段，需要根据实际情况调整
      // 这里暂时只检查is_superuser
      return false;
    });
    
    if (!hasRequiredRole) {
      return <Navigate to="/unauthorized" replace />;
    }
  }

  return <>{children}</>;
};
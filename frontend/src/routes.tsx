import React from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { TokenExpiryDialog } from './components/TokenExpiryDialog';
import { useUIStore } from './stores/index';
import DemoPage from './pages/DemoPage';
import UserPage from './pages/UserPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ProfilePage from './pages/ProfilePage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import TaskManagementPage from './pages/TaskManagementPage';
import SystemMonitoringPage from './pages/SystemMonitoringPage';
import ChatPage from './pages/ChatPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import KnowledgeDocumentDetailPage from './pages/KnowledgeDocumentDetailPage';

const AppRoutes: React.FC = () => {
  const navigate = useNavigate();
  const { tokenExpiryDialogOpen, hideTokenExpiryDialog } = useUIStore();

  const handleTokenExpiryConfirm = () => {
    hideTokenExpiryDialog();
    navigate('/login');
  };

  return (
    <>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        
        {/* 公共路由 */}
        <Route path="/login" element={
          <ProtectedRoute requireAuth={false}>
            <LoginPage />
          </ProtectedRoute>
        } />
        <Route path="/register" element={
          <ProtectedRoute requireAuth={false}>
            <RegisterPage />
          </ProtectedRoute>
        } />
        
        {/* 密码重置相关路由 */}
        <Route path="/forgot-password" element={
          <ProtectedRoute requireAuth={false}>
            <ForgotPasswordPage />
          </ProtectedRoute>
        } />
        <Route path="/reset-password" element={
          <ProtectedRoute requireAuth={false}>
            <ResetPasswordPage />
          </ProtectedRoute>
        } />
        
        {/* 受保护的路由 */}
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        } />
        <Route path="/profile" element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        } />
        <Route path="/user" element={
          <ProtectedRoute>
            <UserPage />
          </ProtectedRoute>
        } />
        <Route path="/demo" element={
          <ProtectedRoute>
            <DemoPage />
          </ProtectedRoute>
        } />
        <Route path="/chat" element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        } />
        
        {/* 综合管理路由 */}
        <Route path="/management" element={<Navigate to="/management/tasks" replace />} />
        <Route path="/management/tasks" element={
          <ProtectedRoute>
            <TaskManagementPage />
          </ProtectedRoute>
        } />
        <Route path="/management/monitoring" element={
          <ProtectedRoute>
            <SystemMonitoringPage />
          </ProtectedRoute>
        } />
        <Route path="/management/knowledge" element={
          <ProtectedRoute>
            <KnowledgeBasePage />
          </ProtectedRoute>
        } />
        <Route path="/management/knowledge/:id" element={
          <ProtectedRoute>
            <KnowledgeDocumentDetailPage />
          </ProtectedRoute>
        } />
        
        {/* 保持向后兼容性 */}
        <Route path="/management/scraper/*" element={<Navigate to="/management/tasks" replace />} />
        <Route path="/scraper/*" element={<Navigate to="/management/tasks" replace />} />

        {/* 管理员路由 (如果用户有is_superuser=true) */}
        {/* <Route path="/admin" element={
          <ProtectedRoute requiredRoles={['admin']}>
            <AdminPage />
          </ProtectedRoute>
        } /> */}
        
        {/* 错误页面 */}
        {/* <Route path="/unauthorized" element={<UnauthorizedPage />} />
        <Route path="*" element={<NotFoundPage />} /> */}
      </Routes>

      {/* Token过期确认对话框 */}
      <TokenExpiryDialog
        open={tokenExpiryDialogOpen}
        onConfirm={handleTokenExpiryConfirm}
      />
    </>
  );
};

export default AppRoutes; 

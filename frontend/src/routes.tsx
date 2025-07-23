import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import DemoPage from './pages/DemoPage';
import UserPage from './pages/UserPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
      <Route path="/demo" element={<DemoPage />} />
      <Route path="/user" element={<UserPage />} />
    </Routes>
  );
};

export default AppRoutes; 
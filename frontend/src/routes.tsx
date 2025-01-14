import React from 'react';
import { Routes, Route } from 'react-router-dom';
import App from './App';
import UserPage from './pages/UserPage';

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<App />} />
      <Route path="/user" element={<UserPage />} />
    </Routes>
  );
};

export default AppRoutes; 
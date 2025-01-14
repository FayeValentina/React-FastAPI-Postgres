import React, { useState } from 'react';
import { Container, Alert, Snackbar } from '@mui/material';
import UserForm from '../components/UserForm';
import api from '../services/api';

interface UserFormData {
  email: string;
  username: string;
  password: string;
  full_name?: string;
  is_active: boolean;
  is_superuser: boolean;
}

const UserPage: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [notification, setNotification] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const handleSubmit = async (data: UserFormData) => {
    setIsLoading(true);
    try {
      await api.post('/users', data);
      setNotification({
        open: true,
        message: 'User created successfully!',
        severity: 'success',
      });
    } catch (error) {
      setNotification({
        open: true,
        message: 'Failed to create user. Please try again.',
        severity: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleCloseNotification = () => {
    setNotification(prev => ({ ...prev, open: false }));
  };

  return (
    <Container>
      <UserForm onSubmit={handleSubmit} isLoading={isLoading} />
      <Snackbar
        open={notification.open}
        autoHideDuration={6000}
        onClose={handleCloseNotification}
      >
        <Alert
          onClose={handleCloseNotification}
          severity={notification.severity}
          sx={{ width: '100%' }}
        >
          {notification.message}
        </Alert>
      </Snackbar>
    </Container>
  );
};

export default UserPage; 
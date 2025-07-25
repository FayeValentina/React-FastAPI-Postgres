import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  Box,
  Alert,
  Grid,
  Avatar,
  Divider,
  CircularProgress,
} from '@mui/material';
import {
  Person as PersonIcon,
  Save as SaveIcon,
  ArrowBack as ArrowBackIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../stores/auth-store';
import MainLayout from '../components/Layout/MainLayout';
import api from '../services/api';

interface ProfileFormData {
  username: string;
  email: string;
  full_name: string;
  age: number | '';
}

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const { user, isAuthenticated, getCurrentUser } = useAuthStore();
  
  const [formData, setFormData] = useState<ProfileFormData>({
    username: '',
    email: '',
    full_name: '',
    age: '',
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    // Initialize form with user data
    if (user) {
      setFormData({
        username: user.username,
        email: user.email,
        full_name: user.full_name || '',
        age: user.age || '',
      });
    }
  }, [isAuthenticated, user, navigate]);

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.username.trim()) {
      errors.username = '请输入用户名';
    } else if (formData.username.length < 3) {
      errors.username = '用户名至少需要3个字符';
    } else if (formData.username.length > 50) {
      errors.username = '用户名不能超过50个字符';
    } else if (!/^[a-zA-Z0-9_-]+$/.test(formData.username)) {
      errors.username = '用户名只能包含字母、数字、下划线和连字符';
    }

    if (!formData.email.trim()) {
      errors.email = '请输入邮箱地址';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errors.email = '请输入有效的邮箱地址';
    }

    if (formData.age !== '' && (formData.age < 0 || formData.age > 150)) {
      errors.age = '年龄必须在0-150之间';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    
    if (name === 'age') {
      const ageValue = value === '' ? '' : parseInt(value, 10);
      setFormData(prev => ({
        ...prev,
        [name]: ageValue,
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [name]: value,
      }));
    }

    // Clear field error when user starts typing
    if (formErrors[name]) {
      setFormErrors(prev => ({
        ...prev,
        [name]: '',
      }));
    }

    // Clear messages
    setError(null);
    setSuccess(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Prepare update data
      const updateData: any = {
        username: formData.username,
        email: formData.email,
        full_name: formData.full_name || null,
      };

      if (formData.age !== '') {
        updateData.age = formData.age;
      }

      // Update user profile
      await api.patch(`/v1/users/${user?.id}`, updateData);
      
      // Refresh user data
      await getCurrentUser();
      
      setSuccess('个人资料更新成功！');
    } catch (error: any) {
      console.error('Profile update failed:', error);
      
      // 401错误由axios拦截器处理，这里只处理其他错误
      if (error.response?.status !== 401) {
        if (error.response?.data?.detail) {
          setError(error.response.data.detail);
        } else if (error.response?.data?.message) {
          setError(error.response.data.message);
        } else {
          setError('更新失败，请稍后重试');
        }
      }
      // 401错误会被axios拦截器自动处理（token刷新或重定向登录）
    } finally {
      setLoading(false);
    }
  };

  if (!isAuthenticated || !user) {
    return null; // Will redirect in useEffect
  }

  return (
    <MainLayout>
      <Container maxWidth="md">
        <Box sx={{ py: 4 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
            <Button
              startIcon={<ArrowBackIcon />}
              onClick={() => navigate('/dashboard')}
              sx={{ mr: 2 }}
            >
              返回仪表板
            </Button>
            <Typography variant="h4">
              编辑个人资料
            </Typography>
          </Box>

          <Grid container spacing={3}>
            {/* Profile Header */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Avatar sx={{ mr: 2, bgcolor: 'primary.main', width: 64, height: 64 }}>
                      <PersonIcon sx={{ fontSize: 32 }} />
                    </Avatar>
                    <Box>
                      <Typography variant="h5" gutterBottom>
                        {user.full_name || user.username}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {user.email}
                      </Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Edit Form */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    基本信息
                  </Typography>
                  
                  <Divider sx={{ mb: 3 }} />

                  {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>
                      {error}
                    </Alert>
                  )}

                  {success && (
                    <Alert severity="success" sx={{ mb: 2 }}>
                      {success}
                    </Alert>
                  )}

                  <Box component="form" onSubmit={handleSubmit}>
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6}>
                        <TextField
                          required
                          fullWidth
                          label="用户名"
                          name="username"
                          value={formData.username}
                          onChange={handleChange}
                          error={!!formErrors.username}
                          helperText={formErrors.username}
                          disabled={loading}
                        />
                      </Grid>
                      
                      <Grid item xs={12} sm={6}>
                        <TextField
                          required
                          fullWidth
                          label="邮箱地址"
                          name="email"
                          type="email"
                          value={formData.email}
                          onChange={handleChange}
                          error={!!formErrors.email}
                          helperText={formErrors.email}
                          disabled={loading}
                        />
                      </Grid>
                      
                      <Grid item xs={12} sm={8}>
                        <TextField
                          fullWidth
                          label="姓名 (可选)"
                          name="full_name"
                          value={formData.full_name}
                          onChange={handleChange}
                          disabled={loading}
                        />
                      </Grid>
                      
                      <Grid item xs={12} sm={4}>
                        <TextField
                          fullWidth
                          label="年龄 (可选)"
                          name="age"
                          type="number"
                          value={formData.age}
                          onChange={handleChange}
                          error={!!formErrors.age}
                          helperText={formErrors.age}
                          disabled={loading}
                          inputProps={{ min: 0, max: 150 }}
                        />
                      </Grid>
                    </Grid>

                    <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
                      <Button
                        type="submit"
                        variant="contained"
                        startIcon={loading ? <CircularProgress size={20} /> : <SaveIcon />}
                        disabled={loading}
                      >
                        {loading ? '保存中...' : '保存更改'}
                      </Button>
                      
                      <Button
                        variant="outlined"
                        onClick={() => navigate('/dashboard')}
                        disabled={loading}
                      >
                        取消
                      </Button>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      </Container>
    </MainLayout>
  );
};

export default ProfilePage;
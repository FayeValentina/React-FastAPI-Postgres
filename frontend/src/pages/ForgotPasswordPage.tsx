import React, { useState, useEffect } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  Link,
  CircularProgress,
  Container,
} from '@mui/material';
import {
  Email as EmailIcon,
  ArrowBack as ArrowBackIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../stores/auth-store';
import { useApiStore } from '../stores/api-store';
import { PasswordResetResponse } from '../types/auth';

const ForgotPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const { postData, getApiState } = useApiStore();
  
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState('');
  const [success, setSuccess] = useState(false);

  // Get API state for forgot password
  const forgotPasswordUrl = '/v1/auth/forgot-password';
  const { loading, error, data } = getApiState(forgotPasswordUrl);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate]);

  const validateEmail = (): boolean => {
    if (!email.trim()) {
      setEmailError('请输入邮箱地址');
      return false;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setEmailError('请输入有效的邮箱地址');
      return false;
    }
    setEmailError('');
    return true;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(e.target.value);
    if (emailError) {
      setEmailError('');
    }
    setSuccess(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateEmail()) {
      return;
    }

    try {
      await postData<PasswordResetResponse>(forgotPasswordUrl, { email });
      setSuccess(true);
    } catch (error) {
      console.error('Forgot password failed:', error);
    }
  };

  const successMessage = success && data 
    ? (data as PasswordResetResponse).message || '重置密码邮件已发送到您的邮箱，请查收。'
    : '重置密码邮件已发送到您的邮箱，请查收。';

  return (
    <Container component="main" maxWidth="sm">
      <Box
        sx={{
          marginTop: 8,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <Card sx={{ width: '100%', maxWidth: { xs: '100%', sm: 420 } }}>
          <CardContent sx={{ p: { xs: 3, sm: 4 } }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <Button
                startIcon={<ArrowBackIcon />}
                onClick={() => navigate('/login')}
                sx={{ mr: 2 }}
                variant="text"
                size="small"
              >
                返回登录
              </Button>
            </Box>

            <Typography component="h1" variant="h4" align="center" gutterBottom>
              忘记密码
            </Typography>
            
            <Typography variant="body2" align="center" color="text.secondary" sx={{ mb: 3 }}>
              {success ? '邮件发送成功' : '请输入您的注册邮箱，我们将发送重置密码链接'}
            </Typography>

            {success ? (
              <Box sx={{ textAlign: 'center' }}>
                <Alert severity="success" sx={{ mb: 2 }}>
                  {successMessage}
                </Alert>
                <Typography variant="body2" sx={{ mb: 3 }}>
                  请检查您的邮箱（包括垃圾邮件文件夹），点击邮件中的链接重置密码。
                </Typography>
                <Button
                  variant="outlined"
                  onClick={() => navigate('/login')}
                  fullWidth
                >
                  返回登录页面
                </Button>
              </Box>
            ) : (
              <>
                {error && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    {error.message || '发送失败，请稍后重试'}
                  </Alert>
                )}

                <Box component="form" onSubmit={handleSubmit} sx={{ mt: 1 }}>
                  <TextField
                    required
                    fullWidth
                    id="email"
                    label="邮箱地址"
                    name="email"
                    autoComplete="email"
                    autoFocus
                    value={email}
                    onChange={handleChange}
                    error={!!emailError}
                    helperText={emailError}
                    disabled={loading}
                    InputProps={{
                      startAdornment: <EmailIcon sx={{ mr: 1, color: 'text.secondary' }} />,
                    }}
                  />
                  
                  <Button
                    type="submit"
                    fullWidth
                    variant="contained"
                    sx={{ mt: 3, mb: 2, py: 1.5 }}
                    disabled={loading}
                    startIcon={loading ? <CircularProgress size={20} /> : null}
                  >
                    {loading ? '发送中...' : '发送重置邮件'}
                  </Button>
                  
                  <Box sx={{ textAlign: 'center', mt: 2 }}>
                    <Typography variant="body2">
                      记起了密码？{' '}
                      <Link component={RouterLink} to="/login" underline="hover">
                        立即登录
                      </Link>
                    </Typography>
                  </Box>
                </Box>
              </>
            )}
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
};

export default ForgotPasswordPage;

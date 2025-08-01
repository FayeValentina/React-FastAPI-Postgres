import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link as RouterLink } from 'react-router-dom';
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
  Grid,
} from '@mui/material';
import {
  Lock as LockIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../stores/auth-store';
import { useApiStore } from '../stores/api-store';
import { PasswordResetResponse } from '../types/auth';

const ResetPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuthStore();
  const { postData, getApiState } = useApiStore();
  
  const [token, setToken] = useState('');
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [tokenMessage, setTokenMessage] = useState('');
  
  const [formData, setFormData] = useState({
    newPassword: '',
    confirmPassword: '',
  });
  
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState(false);

  // API states
  const verifyTokenUrl = '/v1/auth/verify-reset-token';
  const resetPasswordUrl = '/v1/auth/reset-password';
  const verifyTokenState = getApiState(verifyTokenUrl);
  const resetPasswordState = getApiState(resetPasswordUrl);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate]);

  // Get token from URL and verify it
  useEffect(() => {
    const verifyToken = async (tokenToVerify: string) => {
      try {
        // Backend expects token as query parameter, not in request body
        const response = await postData<PasswordResetResponse>(`${verifyTokenUrl}?token=${tokenToVerify}`, {});
        setTokenValid(response.success !== false);
        setTokenMessage(response.message);
      } catch (verifyError) {
        setTokenValid(false);
        setTokenMessage('令牌验证失败');
        console.error('Token verification failed:', verifyError);
      }
    };

    const tokenFromUrl = searchParams.get('token');
    if (tokenFromUrl) {
      setToken(tokenFromUrl);
      verifyToken(tokenFromUrl);
    } else {
      setTokenValid(false);
      setTokenMessage('重置链接无效或已过期');
    }
  }, [searchParams, postData]);

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.newPassword) {
      errors.newPassword = '请输入新密码';
    } else if (formData.newPassword.length < 8) {
      errors.newPassword = '密码至少需要8个字符';
    }

    if (!formData.confirmPassword) {
      errors.confirmPassword = '请确认新密码';
    } else if (formData.confirmPassword !== formData.newPassword) {
      errors.confirmPassword = '两次输入的密码不一致';
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));

    // Clear field error when user starts typing
    if (formErrors[name]) {
      setFormErrors(prev => ({
        ...prev,
        [name]: '',
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      await postData<PasswordResetResponse>(resetPasswordUrl, {
        token,
        new_password: formData.newPassword,
      });
      setSuccess(true);
    } catch (error) {
      console.error('Reset password failed:', error);
    }
  };

  // Loading state for token verification
  if (tokenValid === null && verifyTokenState.loading) {
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
          <Card sx={{ width: '100%', maxWidth: 400 }}>
            <CardContent sx={{ p: 4, textAlign: 'center' }}>
              <CircularProgress sx={{ mb: 2 }} />
              <Typography variant="body1">
                正在验证重置链接...
              </Typography>
            </CardContent>
          </Card>
        </Box>
      </Container>
    );
  }

  // Invalid token
  if (tokenValid === false) {
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
          <Card sx={{ width: '100%', maxWidth: 400 }}>
            <CardContent sx={{ p: 4, textAlign: 'center' }}>
              <Alert severity="error" sx={{ mb: 2 }}>
                {tokenMessage}
              </Alert>
              <Typography variant="body2" sx={{ mb: 3 }}>
                请重新申请密码重置或返回登录页面。
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Button
                    variant="outlined"
                    onClick={() => navigate('/forgot-password')}
                    fullWidth
                  >
                    重新申请
                  </Button>
                </Grid>
                <Grid item xs={6}>
                  <Button
                    variant="contained"
                    onClick={() => navigate('/login')}
                    fullWidth
                  >
                    返回登录
                  </Button>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Box>
      </Container>
    );
  }

  // Success state
  if (success) {
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
          <Card sx={{ width: '100%', maxWidth: 400 }}>
            <CardContent sx={{ p: 4, textAlign: 'center' }}>
              <CheckCircleIcon sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
              <Typography variant="h5" gutterBottom>
                密码重置成功
              </Typography>
              <Typography variant="body2" sx={{ mb: 3 }}>
                您的密码已成功重置，请使用新密码登录。
              </Typography>
              <Button
                variant="contained"
                onClick={() => navigate('/login')}
                fullWidth
              >
                前往登录
              </Button>
            </CardContent>
          </Card>
        </Box>
      </Container>
    );
  }

  // Reset password form
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
        <Card sx={{ width: '100%', maxWidth: 400 }}>
          <CardContent sx={{ p: 4 }}>
            <Typography component="h1" variant="h4" align="center" gutterBottom>
              重置密码
            </Typography>
            
            <Typography variant="body2" align="center" color="text.secondary" sx={{ mb: 3 }}>
              请输入您的新密码
            </Typography>

            {resetPasswordState.error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {resetPasswordState.error.message || '重置失败，请稍后重试'}
              </Alert>
            )}

            <Box component="form" onSubmit={handleSubmit} sx={{ mt: 1 }}>
              <TextField
                required
                fullWidth
                name="newPassword"
                label="新密码"
                type="password"
                id="newPassword"
                autoComplete="new-password"
                autoFocus
                value={formData.newPassword}
                onChange={handleChange}
                error={!!formErrors.newPassword}
                helperText={formErrors.newPassword}
                disabled={resetPasswordState.loading}
                sx={{ mb: 2 }}
                InputProps={{
                  startAdornment: <LockIcon sx={{ mr: 1, color: 'text.secondary' }} />,
                }}
              />
              
              <TextField
                required
                fullWidth
                name="confirmPassword"
                label="确认新密码"
                type="password"
                id="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                error={!!formErrors.confirmPassword}
                helperText={formErrors.confirmPassword}
                disabled={resetPasswordState.loading}
              />
              
              <Button
                type="submit"
                fullWidth
                variant="contained"
                sx={{ mt: 3, mb: 2, py: 1.5 }}
                disabled={resetPasswordState.loading}
                startIcon={resetPasswordState.loading ? <CircularProgress size={20} /> : null}
              >
                {resetPasswordState.loading ? '重置中...' : '重置密码'}
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
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
};

export default ResetPasswordPage;
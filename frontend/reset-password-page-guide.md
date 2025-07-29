# 前端添加密码重置功能实现文档

## 概述

基于后端新增的三个密码重置端点：
- `POST /api/v1/auth/forgot-password` - 发送重置邮件
- `GET /api/v1/auth/verify-reset-token?token=xxx` - 验证重置令牌
- `POST /api/v1/auth/reset-password` - 重置密码

前端需要添加相应的页面和功能，使用 `api-store` 统一管理API调用状态。

## 实现步骤

### 步骤1：扩展类型定义

**文件：** `frontend/src/types/auth.ts`

```typescript
// 在现有内容后添加以下类型定义

// 忘记密码请求
export interface ForgotPasswordRequest {
  email: string;
}

// 验证重置令牌响应
export interface VerifyResetTokenResponse {
  message: string;
  success: boolean;
}

// 重置密码请求
export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

// 通用API响应（如果还没有的话）
export interface ApiResponse {
  message: string;
  success?: boolean;
}
```

### 步骤2：创建忘记密码页面

**文件：** `frontend/src/pages/ForgotPasswordPage.tsx`

```typescript
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
import { ApiResponse } from '../types/auth';

const ForgotPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  
  // 使用 api-store 管理API状态
  const forgotPasswordState = useApiStore(state => 
    state.apiStates['/v1/auth/forgot-password'] || { data: null, loading: false, error: null }
  );
  const { fetchData, clearError } = useApiStore();
  
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState('');
  const [success, setSuccess] = useState(false);

  const { loading, error } = forgotPasswordState;

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate]);

  // Clear error when user starts typing
  useEffect(() => {
    if (error && email) {
      clearError('/v1/auth/forgot-password');
    }
  }, [email, error, clearError]);

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
    if (error) {
      clearError('/v1/auth/forgot-password');
    }
    setSuccess(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateEmail()) {
      return;
    }

    try {
      const response = await fetchData<ApiResponse>('/v1/auth/forgot-password', {
        method: 'POST',
        data: { email }
      });
      setSuccess(true);
    } catch (error) {
      console.error('Forgot password failed:', error);
    }
  };

  const successMessage = success && forgotPasswordState.data 
    ? (forgotPasswordState.data as ApiResponse).message || '重置密码邮件已发送到您的邮箱，请查收。'
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
        <Card sx={{ width: '100%', maxWidth: 400 }}>
          <CardContent sx={{ p: 4 }}>
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
```

### 步骤3：创建重置密码页面

**文件：** `frontend/src/pages/ResetPasswordPage.tsx`

```typescript
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
import { VerifyResetTokenResponse, ApiResponse } from '../types/auth';

const ResetPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { isAuthenticated } = useAuthStore();
  const { fetchData, clearError } = useApiStore();
  
  // API状态管理
  const verifyTokenState = useApiStore(state => 
    state.apiStates[`/v1/auth/verify-reset-token`] || { data: null, loading: false, error: null }
  );
  const resetPasswordState = useApiStore(state => 
    state.apiStates['/v1/auth/reset-password'] || { data: null, loading: false, error: null }
  );
  
  const [token, setToken] = useState('');
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);
  const [tokenMessage, setTokenMessage] = useState('');
  
  const [formData, setFormData] = useState({
    newPassword: '',
    confirmPassword: '',
  });
  
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState(false);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate]);

  // Get token from URL and verify it
  useEffect(() => {
    const tokenFromUrl = searchParams.get('token');
    if (tokenFromUrl) {
      setToken(tokenFromUrl);
      verifyToken(tokenFromUrl);
    } else {
      setTokenValid(false);
      setTokenMessage('重置链接无效或已过期');
    }
  }, [searchParams]);

  const verifyToken = async (tokenToVerify: string) => {
    try {
      const response = await fetchData<VerifyResetTokenResponse>(
        `/v1/auth/verify-reset-token?token=${tokenToVerify}`
      );
      setTokenValid(response.success);
      setTokenMessage(response.message);
    } catch (error) {
      setTokenValid(false);
      setTokenMessage('令牌验证失败');
    }
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.newPassword) {
      errors.newPassword = '请输入新密码';
    } else if (formData.newPassword.length < 6) {
      errors.newPassword = '密码至少需要6个字符';
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

    if (resetPasswordState.error) {
      clearError('/v1/auth/reset-password');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    try {
      await fetchData<ApiResponse>('/v1/auth/reset-password', {
        method: 'POST',
        data: {
          token,
          new_password: formData.newPassword,
        }
      });
      setSuccess(true);
    } catch (error) {
      console.error('Reset password failed:', error);
    }
  };

  // Loading state for token verification
  if (tokenValid === null) {
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
```

### 步骤4：更新登录页面

**文件：** `frontend/src/pages/LoginPage.tsx`

在现有的登录页面表单底部，找到这段代码：
```typescript
<Box sx={{ textAlign: 'center', mt: 2 }}>
  <Typography variant="body2">
    还没有账户？{' '}
    <Link component={RouterLink} to="/register" underline="hover">
      立即注册
    </Link>
  </Typography>
</Box>
```

替换为：
```typescript
<Box sx={{ textAlign: 'center', mt: 2 }}>
  <Typography variant="body2">
    还没有账户？{' '}
    <Link component={RouterLink} to="/register" underline="hover">
      立即注册
    </Link>
  </Typography>
  <Typography variant="body2" sx={{ mt: 1 }}>
    忘记密码？{' '}
    <Link component={RouterLink} to="/forgot-password" underline="hover">
      点击重置
    </Link>
  </Typography>
</Box>
```

### 步骤5：更新路由配置

**文件：** `frontend/src/routes.tsx`

在文件顶部添加导入：
```typescript
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
```

在路由配置中添加新路由：
```typescript
const AppRoutes: React.FC = () => {
  // ... existing code

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
        
        {/* 新增：密码重置相关路由 */}
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
        
        {/* ... 其他现有路由保持不变 */}
      </Routes>
      
      {/* ... existing components */}
    </>
  );
};
```

## 功能说明

### 完整的密码重置流程：

1. **忘记密码页面** (`/forgot-password`)
   - 用户输入邮箱地址
   - 调用 `POST /api/v1/auth/forgot-password`
   - 显示成功消息并引导用户查收邮件

2. **重置密码页面** (`/reset-password?token=xxx`)
   - 从URL参数获取重置令牌
   - 调用 `GET /api/v1/auth/verify-reset-token` 验证令牌
   - 如果令牌有效，显示密码重置表单
   - 调用 `POST /api/v1/auth/reset-password` 完成重置

3. **登录页面更新**
   - 添加"忘记密码"链接，引导用户到重置流程

### 技术特点：

- ✅ **统一的状态管理**：使用 `api-store` 管理所有API调用状态
- ✅ **完整的错误处理**：统一的错误处理和用户反馈
- ✅ **表单验证**：前端验证确保数据质量
- ✅ **响应式设计**：适配不同屏幕尺寸
- ✅ **良好的UX**：清晰的状态提示和用户引导
- ✅ **架构一致性**：与现有项目架构保持一致

### 用户体验流程：

1. 用户在登录页点击"忘记密码"
2. 进入忘记密码页面，输入邮箱
3. 收到重置邮件，点击邮件中的链接
4. 跳转到重置密码页面，系统自动验证令牌
5. 如果令牌有效，用户输入新密码
6. 重置成功，跳转回登录页面

这样就完成了完整的密码重置功能集成。
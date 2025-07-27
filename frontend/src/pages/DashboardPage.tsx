import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Avatar,
  Chip,
  Grid,
  Alert,
} from '@mui/material';
import {
  Person as PersonIcon,
  ExitToApp as LogoutIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../stores/auth-store';
import MainLayout from '../components/Layout/MainLayout';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const { user, logout, error } = useAuthStore();

  const handleLogout = async () => {
    try {
      await logout();
      // 自动重定向由 ProtectedRoute 处理
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // 不再需要认证检查和用户信息获取
  // ProtectedRoute 和 AuthProvider 已经处理了

  return (
    <MainLayout>
      <Box sx={{ maxWidth: 1200, mx: 'auto', p: 3 }}>
        <Typography variant="h4" gutterBottom>
          用户仪表板
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          {/* User Profile Card */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <Avatar sx={{ mr: 2, bgcolor: 'primary.main' }}>
                    <PersonIcon />
                  </Avatar>
                  <Typography variant="h5">
                    用户信息
                  </Typography>
                </Box>

                {user && (
                  <Box>
                    <Typography variant="body1" sx={{ mb: 1 }}>
                      <strong>用户名:</strong> {user.username}
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 1 }}>
                      <strong>邮箱:</strong> {user.email}
                    </Typography>
                    {user.full_name && (
                      <Typography variant="body1" sx={{ mb: 1 }}>
                        <strong>姓名:</strong> {user.full_name}
                      </Typography>
                    )}
                    {user.age && (
                      <Typography variant="body1" sx={{ mb: 1 }}>
                        <strong>年龄:</strong> {user.age}
                      </Typography>
                    )}
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      <strong>注册时间:</strong> {formatDate(user.created_at)}
                    </Typography>

                    <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                      <Chip
                        label={user.is_active ? '活跃' : '未激活'}
                        color={user.is_active ? 'success' : 'default'}
                        size="small"
                      />
                      {user.is_superuser && (
                        <Chip
                          label="管理员"
                          color="warning"
                          size="small"
                        />
                      )}
                    </Box>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Quick Actions Card */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  快速操作
                </Typography>
                
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Button
                    variant="outlined"
                    startIcon={<PersonIcon />}
                    onClick={() => navigate('/profile')}
                    fullWidth
                  >
                    编辑个人资料
                  </Button>
                  
                  <Button
                    variant="outlined"
                    onClick={() => navigate('/user')}
                    fullWidth
                  >
                    用户管理
                  </Button>
                  
                  <Button
                    variant="contained"
                    color="error"
                    startIcon={<LogoutIcon />}
                    onClick={handleLogout}
                    fullWidth
                    sx={{ mt: 2 }}
                  >
                    退出登录
                  </Button>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Welcome Message */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h5" gutterBottom>
                  欢迎回来！
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  {user?.full_name || user?.username}，欢迎使用我们的系统。
                  这是一个基于 React + FastAPI + PostgreSQL 的全栈应用示例。
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    </MainLayout>
  );
};

export default DashboardPage;
import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  Card,
  CardContent,
  Box,
  Button,
  Grid,
} from '@mui/material';
import {
  Person as PersonIcon,
  Add as AddIcon,
  List as ListIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import MainLayout from '../components/Layout/MainLayout';

const UserPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
    }
  }, [isAuthenticated, navigate]);

  if (!isAuthenticated) {
    return null;
  }

  return (
    <MainLayout>
      <Container maxWidth="lg">
        <Box sx={{ py: 4 }}>
          <Typography variant="h4" gutterBottom>
            用户管理
          </Typography>
          
          <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
            管理系统用户和相关设置
          </Typography>

          <Grid container spacing={3}>
            {/* Current User Info */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <PersonIcon sx={{ mr: 2, color: 'primary.main' }} />
                    <Typography variant="h6">
                      当前用户信息
                    </Typography>
                  </Box>
                  
                  {user && (
                    <Box>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        <strong>用户名:</strong> {user.username}
                      </Typography>
                      <Typography variant="body2" sx={{ mb: 1 }}>
                        <strong>邮箱:</strong> {user.email}
                      </Typography>
                      {user.full_name && (
                        <Typography variant="body2" sx={{ mb: 1 }}>
                          <strong>姓名:</strong> {user.full_name}
                        </Typography>
                      )}
                      <Typography variant="body2">
                        <strong>权限:</strong> {user.is_superuser ? '管理员' : '普通用户'}
                      </Typography>
                    </Box>
                  )}
                </CardContent>
              </Card>
            </Grid>

            {/* User Management Actions */}
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    用户操作
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
                    
                    {user?.is_superuser && (
                      <>
                        <Button
                          variant="outlined"
                          startIcon={<AddIcon />}
                          onClick={() => {/* TODO: 添加创建用户功能 */}}
                          fullWidth
                          disabled
                        >
                          创建新用户 (TODO)
                        </Button>
                        
                        <Button
                          variant="outlined"
                          startIcon={<ListIcon />}
                          onClick={() => {/* TODO: 添加用户列表功能 */}}
                          fullWidth
                          disabled
                        >
                          用户列表 (TODO)
                        </Button>
                      </>
                    )}
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Quick Actions */}
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    快速导航
                  </Typography>
                  
                  <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                    <Button
                      variant="contained"
                      onClick={() => navigate('/dashboard')}
                    >
                      返回仪表板
                    </Button>
                    
                    <Button
                      variant="outlined"
                      onClick={() => navigate('/demo')}
                    >
                      API 演示
                    </Button>
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

export default UserPage; 
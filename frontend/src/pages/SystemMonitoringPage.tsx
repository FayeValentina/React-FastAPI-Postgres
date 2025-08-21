import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Grid,
  Alert,
  Card,
  CardContent,
  Paper,
  Chip,
  LinearProgress,
  Button,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  HealthAndSafety as HealthIcon,
  Assessment as StatsIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { useApiStore } from '../stores/api-store';
import { useAuthStore } from '../stores/auth-store';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import AutoRefreshControl from '../components/Common/AutoRefreshControl';
import ManagementLayout from '../components/Layout/ManagementLayout';
import SystemStatusCard from '../components/Tasks/SystemStatusCard';
import SystemHealthPanel from '../components/Tasks/SystemHealthPanel';
import ExecutionStatsPanel from '../components/Tasks/ExecutionStatsPanel';
import { SystemStatus, SystemHealth } from '../types/task';

const SystemMonitoringPage: React.FC = () => {
  const { fetchData, getApiState } = useApiStore();
  const { user } = useAuthStore();
  
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(30000);

  const statusUrl = '/v1/tasks/system/status';
  const healthUrl = '/v1/tasks/system/health';
  
  const { loading: statusLoading } = getApiState(statusUrl);
  const { loading: healthLoading } = getApiState(healthUrl);

  const isSuperuser = user?.is_superuser || false;

  const loadSystemData = useCallback(async () => {
    if (!isSuperuser) return;
    
    try {
      const [statusData, healthData] = await Promise.all([
        fetchData<SystemStatus>(statusUrl),
        fetchData<SystemHealth>(healthUrl),
      ]);
      
      setSystemStatus(statusData);
      setSystemHealth(healthData);
    } catch (error) {
      console.error('Failed to load system data:', error);
    }
  }, [fetchData, statusUrl, healthUrl, isSuperuser]);

  const autoRefresh = useAutoRefresh(
    loadSystemData,
    {
      interval: autoRefreshInterval,
      enabled: true,
      immediate: isSuperuser,
    }
  );

  const getHealthColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'degraded': return 'warning';
      case 'unhealthy': return 'error';
      default: return 'default';
    }
  };

  const getHealthIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <SuccessIcon />;
      case 'degraded': return <WarningIcon />;
      case 'unhealthy': return <ErrorIcon />;
      default: return <HealthIcon />;
    }
  };

  if (!isSuperuser) {
    return (
      <ManagementLayout>
        <Alert severity="error" sx={{ mt: 4 }}>
          您没有权限访问系统监控功能。需要超级管理员权限。
        </Alert>
      </ManagementLayout>
    );
  }

  const loading = statusLoading || healthLoading;

  return (
    <ManagementLayout>
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" gutterBottom>
            系统监控中心
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Button
              variant="outlined"
              onClick={() => window.location.href = '/management/tasks'}
            >
              任务管理
            </Button>
            <AutoRefreshControl
              isRunning={autoRefresh.isRunning}
              interval={autoRefreshInterval}
              onToggle={autoRefresh.toggle}
              onRefresh={autoRefresh.refresh}
              onSetInterval={setAutoRefreshInterval}
              disabled={loading}
            />
          </Box>
        </Box>

        {/* 系统健康状态 */}
        {systemHealth && (
          <Paper sx={{ p: 2, mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              {getHealthIcon(systemHealth.status)}
              <Typography variant="h6">系统健康状态</Typography>
              <Chip
                label={systemHealth.status.toUpperCase()}
                color={getHealthColor(systemHealth.status) as any}
                size="small"
              />
              <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto' }}>
                {new Date(systemHealth.timestamp).toLocaleString('zh-CN')}
              </Typography>
            </Box>
            
            {systemHealth.status !== 'healthy' && (
              <Box sx={{ mt: 2 }}>
                {Object.entries(systemHealth.components).map(([name, component]) => 
                  component.status !== 'healthy' && (
                    <Alert key={name} severity="warning" sx={{ mb: 1 }}>
                      <strong>{name}:</strong> {component.message}
                    </Alert>
                  )
                )}
              </Box>
            )}
          </Paper>
        )}

        {/* 系统状态概览 */}
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <DashboardIcon sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
                <Typography variant="h4" color="primary">
                  {systemStatus?.config_stats.total_configs || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  任务配置总数
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <StatsIcon sx={{ fontSize: 40, color: 'success.main', mb: 1 }} />
                <Typography variant="h4" color="success.main">
                  {systemStatus?.schedule_summary.active_tasks || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  活跃任务
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="info.main">
                  {systemStatus?.execution_stats.success_rate.toFixed(1) || 0}%
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  执行成功率
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={systemStatus?.execution_stats.success_rate || 0}
                  sx={{ mt: 1 }}
                />
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card>
              <CardContent sx={{ textAlign: 'center' }}>
                <Typography variant="h4" color="warning.main">
                  {systemStatus?.execution_stats.avg_duration_seconds.toFixed(1) || 0}s
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  平均执行时间
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* 详细状态面板 */}
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <SystemStatusCard status={systemStatus} />
          </Grid>
          <Grid item xs={12} md={6}>
            <SystemHealthPanel health={systemHealth} />
          </Grid>
          <Grid item xs={12}>
            <ExecutionStatsPanel />
          </Grid>
        </Grid>
      </Box>
    </ManagementLayout>
  );
};

export default SystemMonitoringPage;
import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  CircularProgress,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  CheckCircle as HealthyIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { SystemInfo } from '../../types/task';

const SystemHealthPanel: React.FC = () => {
  const { fetchData, getApiState } = useApiStore();
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);

  const systemUrl = '/v1/tasks/system?include_health=true&include_stats=true';
  const { loading, error } = getApiState(systemUrl);

  useEffect(() => {
    loadSystemInfo();
    const interval = setInterval(loadSystemInfo, 30000); // 每30秒刷新
    return () => clearInterval(interval);
  }, []);

  const loadSystemInfo = async () => {
    try {
      const data = await fetchData<SystemInfo>(systemUrl);
      setSystemInfo(data);
    } catch (error) {
      console.error('Failed to load system info:', error);
    }
  };

  if (loading && !systemInfo) {
    return (
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </CardContent>
      </Card>
    );
  }

  if (error || !systemInfo) {
    return null;
  }

  const healthScore = systemInfo.health?.health_score || 0;
  const healthColor = healthScore >= 0.8 ? 'success' : healthScore >= 0.5 ? 'warning' : 'error';
  const healthIcon = healthScore >= 0.8 ? <HealthyIcon /> : healthScore >= 0.5 ? <WarningIcon /> : <ErrorIcon />;

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          系统健康状态
          <Chip
            icon={healthIcon}
            label={`${(healthScore * 100).toFixed(0)}%`}
            color={healthColor}
            size="small"
          />
        </Typography>

        <LinearProgress 
          variant="determinate" 
          value={healthScore * 100} 
          color={healthColor}
          sx={{ mb: 2, height: 8, borderRadius: 1 }}
        />

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 2 }}>
          {systemInfo.stats && (
            <>
              <Box>
                <Typography variant="caption" color="text.secondary">调度器状态</Typography>
                <Typography variant="body1">
                  <Chip
                    label={systemInfo.stats.scheduler_running ? '运行中' : '已停止'}
                    color={systemInfo.stats.scheduler_running ? 'success' : 'error'}
                    size="small"
                  />
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">总任务数</Typography>
                <Typography variant="h6">{systemInfo.stats.total_jobs}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">活跃任务</Typography>
                <Typography variant="h6">{systemInfo.stats.active_jobs}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">暂停任务</Typography>
                <Typography variant="h6">{systemInfo.stats.paused_jobs}</Typography>
              </Box>
            </>
          )}
        </Box>

        {systemInfo.health?.unhealthy_jobs && systemInfo.health.unhealthy_jobs.length > 0 && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              异常任务 ({systemInfo.health.unhealthy_jobs.length})
            </Typography>
            {systemInfo.health.unhealthy_jobs.slice(0, 3).map((job) => (
              <Typography key={job.job_id} variant="caption" display="block">
                • {job.name} - {job.status}
              </Typography>
            ))}
            {systemInfo.health.unhealthy_jobs.length > 3 && (
              <Typography variant="caption" display="block">
                ...还有 {systemInfo.health.unhealthy_jobs.length - 3} 个异常任务
              </Typography>
            )}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};

export default SystemHealthPanel;
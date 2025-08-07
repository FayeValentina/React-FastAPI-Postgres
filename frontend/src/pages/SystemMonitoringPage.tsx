import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Grid,
  Alert,
  Paper,
  Card,
  CardContent,
  CardHeader,
  IconButton,
  Chip,
  Divider,
  useTheme,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Dashboard as DashboardIcon,
  PlayArrow as ActiveIcon,
  Event as EventIcon,
  TrendingUp as StatsIcon,
  HealthAndSafety as HealthIcon,
  Memory as SystemIcon,
  Speed as PerformanceIcon,
} from '@mui/icons-material';
import { useApiStore } from '../stores/api-store';
import { useAuthStore } from '../stores/auth-store';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import AutoRefreshControl from '../components/Common/AutoRefreshControl';
import ManagementLayout from '../components/Layout/ManagementLayout';
import SystemHealthPanel from '../components/Tasks/SystemHealthPanel';
import ActiveTasksPanel from '../components/Tasks/ActiveTasksPanel';
import ScheduleEventsPanel from '../components/Tasks/ScheduleEventsPanel';
import ExecutionStatsPanel from '../components/Tasks/ExecutionStatsPanel';
import SystemAnalysisPanel from '../components/Tasks/SystemAnalysisPanel';
import { 
  SystemInfo, 
  ActiveTask, 
  ScheduleEvent, 
  ExecutionStatsResponse, 
  SystemAnalysis 
} from '../types/task';

const SystemMonitoringPage: React.FC = () => {
  const theme = useTheme();
  const { fetchData, getApiState } = useApiStore();
  const { user } = useAuthStore();
  
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [systemAnalysis, setSystemAnalysis] = useState<SystemAnalysis | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(30000); // 30秒

  // API URLs
  const systemInfoUrl = '/v1/tasks';
  const systemAnalysisUrl = '/v1/tasks/analysis';
  
  const { loading: systemLoading, error: systemError } = getApiState(systemInfoUrl);
  const { loading: analysisLoading } = getApiState(systemAnalysisUrl);

  // Check if user is superuser
  const isSuperuser = user?.is_superuser || false;

  const loadSystemData = useCallback(async () => {
    if (!isSuperuser) return;
    
    try {
      const [infoData, analysisData] = await Promise.all([
        fetchData<SystemInfo>(systemInfoUrl),
        fetchData<SystemAnalysis>(systemAnalysisUrl),
      ]);
      
      setSystemInfo(infoData);
      setSystemAnalysis(analysisData);
      setLastRefresh(new Date());
    } catch (error) {
      console.error('Failed to load system data:', error);
    }
  }, [fetchData, systemInfoUrl, systemAnalysisUrl, isSuperuser]);

  const handleRefresh = useCallback(async () => {
    await loadSystemData();
    setRefreshTrigger(prev => prev + 1);
  }, [loadSystemData]);

  // 使用自动刷新Hook
  const autoRefresh = useAutoRefresh(
    handleRefresh,
    {
      interval: autoRefreshInterval,
      enabled: true,
      immediate: isSuperuser,
    }
  );

  // 处理刷新间隔变化
  const handleIntervalChange = useCallback((newInterval: number) => {
    setAutoRefreshInterval(newInterval);
    autoRefresh.setInterval(newInterval);
  }, [autoRefresh]);

  const renderSystemOverview = () => {
    const stats = systemInfo?.stats;
    const health = systemInfo?.health;
    
    if (!stats && !health) return null;

    return (
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {/* System Status Cards */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ textAlign: 'center' }}>
              <SystemIcon sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
              <Typography variant="h4" color="primary">
                {stats?.total_jobs || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                总任务数
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ textAlign: 'center' }}>
              <ActiveIcon sx={{ fontSize: 40, color: 'success.main', mb: 1 }} />
              <Typography variant="h4" color="success.main">
                {stats?.active_jobs || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                活跃任务
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ textAlign: 'center' }}>
              <PerformanceIcon sx={{ fontSize: 40, color: 'warning.main', mb: 1 }} />
              <Typography variant="h4" color="warning.main">
                {stats?.paused_jobs || 0}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                暂停任务
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ textAlign: 'center' }}>
              <HealthIcon sx={{ 
                fontSize: 40, 
                color: health && health.health_score >= 80 ? 'success.main' : 
                       health && health.health_score >= 60 ? 'warning.main' : 'error.main',
                mb: 1 
              }} />
              <Typography variant="h4" color={
                health && health.health_score >= 80 ? 'success.main' : 
                health && health.health_score >= 60 ? 'warning.main' : 'error.main'
              }>
                {health ? `${health.health_score}%` : 'N/A'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                健康评分
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Scheduler Status */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <DashboardIcon />
                  <Typography variant="h6">调度器状态</Typography>
                  <Chip 
                    label={stats?.scheduler_running ? '运行中' : '已停止'}
                    color={stats?.scheduler_running ? 'success' : 'error'}
                    size="small"
                  />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  最后更新: {lastRefresh.toLocaleTimeString('zh-CN')}
                </Typography>
              </Box>
              {health && health.unhealthy_jobs && health.unhealthy_jobs.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" color="error" gutterBottom>
                    不健康的任务 ({health.unhealthy_jobs.length}):
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {health.unhealthy_jobs.slice(0, 5).map((job, index) => (
                      <Chip 
                        key={index}
                        label={`${job.name} (${job.status})`}
                        size="small"
                        color="error"
                        variant="outlined"
                      />
                    ))}
                    {health.unhealthy_jobs.length > 5 && (
                      <Chip 
                        label={`+${health.unhealthy_jobs.length - 5} 更多`}
                        size="small"
                        variant="outlined"
                      />
                    )}
                  </Box>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    );
  };

  const renderSystemAnalysis = () => {
    if (!systemAnalysis) return null;

    const { schedule_distribution } = systemAnalysis;

    return (
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader
              title="调度分析"
              avatar={<TrendingUp />}
            />
            <CardContent>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  调度任务总数
                </Typography>
                <Typography variant="h5">
                  {schedule_distribution.total_bot_schedules}
                </Typography>
              </Box>
              
              <Divider sx={{ my: 2 }} />
              
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  高峰时段
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {schedule_distribution.peak_hours.map(hour => (
                    <Chip key={hour} label={`${hour}:00`} size="small" />
                  ))}
                </Box>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  每小时最大任务数
                </Typography>
                <Typography variant="body1">
                  {schedule_distribution.max_tasks_per_hour}
                </Typography>
              </Box>

              {schedule_distribution.optimization_needed && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  系统检测到需要优化调度分布
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader
              title="优化建议"
              avatar={<HealthIcon />}
            />
            <CardContent>
              {schedule_distribution.recommendations.length > 0 ? (
                <Box>
                  {schedule_distribution.recommendations.map((recommendation, index) => (
                    <Alert key={index} severity="info" sx={{ mb: 1 }}>
                      {recommendation}
                    </Alert>
                  ))}
                </Box>
              ) : (
                <Alert severity="success">
                  当前调度配置良好，无需优化建议
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    );
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

  return (
    <ManagementLayout>
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" gutterBottom>
            系统监控
          </Typography>
          <AutoRefreshControl
            isRunning={autoRefresh.isRunning}
            interval={autoRefreshInterval}
            onStart={autoRefresh.start}
            onStop={autoRefresh.stop}
            onToggle={autoRefresh.toggle}
            onRefresh={autoRefresh.refresh}
            onSetInterval={handleIntervalChange}
            disabled={systemLoading || analysisLoading}
          />
        </Box>

        {systemError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {systemError.message || '加载系统信息失败'}
          </Alert>
        )}

        {/* System Overview */}
        {renderSystemOverview()}

        {/* System Analysis */}
        {renderSystemAnalysis()}

        {/* Monitoring Panels */}
        <Grid container spacing={3}>
          {/* System Health Panel */}
          <Grid item xs={12}>
            <SystemHealthPanel refreshTrigger={refreshTrigger} />
          </Grid>

          {/* Active Tasks Panel */}
          <Grid item xs={12} lg={6}>
            <ActiveTasksPanel refreshTrigger={refreshTrigger} />
          </Grid>

          {/* Schedule Events Panel */}
          <Grid item xs={12} lg={6}>
            <ScheduleEventsPanel refreshTrigger={refreshTrigger} />
          </Grid>

          {/* Execution Stats Panel */}
          <Grid item xs={12}>
            <ExecutionStatsPanel refreshTrigger={refreshTrigger} />
          </Grid>

          {/* System Analysis Panel */}
          <Grid item xs={12}>
            <SystemAnalysisPanel refreshTrigger={refreshTrigger} />
          </Grid>
        </Grid>
      </Box>
    </ManagementLayout>
  );
};

export default SystemMonitoringPage;
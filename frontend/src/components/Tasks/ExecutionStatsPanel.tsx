import React, { useEffect, useState, useCallback } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  Alert,
  IconButton,
  Grid,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
} from '@mui/material';
import {
  TrendingUp as StatsIcon,
  Refresh as RefreshIcon,
  Timeline as TimelineIcon,
  Assessment as AssessmentIcon,
  Speed as PerformanceIcon,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import { useApiStore } from '../../stores/api-store';
import { ExecutionStats } from '../../types/task';

interface ExecutionStatsPanelProps {
  refreshTrigger?: number;
}

const ExecutionStatsPanel: React.FC<ExecutionStatsPanelProps> = ({ refreshTrigger = 0 }) => {
  const { fetchData, getApiState } = useApiStore();
  
  const [stats, setStats] = useState<ExecutionStats | null>(null);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('7d');
  const [viewMode, setViewMode] = useState<'overview' | 'trends' | 'details'>('overview');

  const buildStatsUrl = () => {
    const params = new URLSearchParams();
    params.append('days', timeRange === '7d' ? '7' : timeRange === '30d' ? '30' : '90');
    return `/v1/tasks/executions/stats?${params.toString()}`;
  };

  const statsUrl = buildStatsUrl();
  const { loading, error } = getApiState(statsUrl);

  const loadStats = useCallback(async () => {
    try {
      const data = await fetchData<ExecutionStats>(statsUrl);
      setStats(data);
    } catch (error) {
      console.error('Failed to load execution stats:', error);
    }
  }, [fetchData, statsUrl]);

  useEffect(() => {
    loadStats();
  }, [loadStats, refreshTrigger, timeRange]);

  const handleTimeRangeChange = (range: '7d' | '30d' | '90d') => {
    setTimeRange(range);
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };



  const renderOverviewCards = () => {
    if (!stats) return null;

    const successRate = stats.success_rate;

    return (
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <StatsIcon sx={{ fontSize: 40, color: 'primary.main', mb: 1 }} />
            <Typography variant="h4" color="primary">
              {stats.total_executions.toLocaleString()}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              总执行次数
            </Typography>
          </Paper>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <AssessmentIcon sx={{ fontSize: 40, color: 'success.main', mb: 1 }} />
            <Typography variant="h4" color="success.main">
              {successRate.toFixed(1)}%
            </Typography>
            <Typography variant="body2" color="text.secondary">
              总体成功率
            </Typography>
            <LinearProgress
              variant="determinate"
              value={successRate}
              sx={{ mt: 1, height: 6, borderRadius: 3 }}
              color="success"
            />
          </Paper>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <PerformanceIcon sx={{ fontSize: 40, color: 'info.main', mb: 1 }} />
            <Typography variant="h4" color="info.main">
              {formatDuration(stats.avg_duration_seconds)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              平均执行时间
            </Typography>
          </Paper>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Paper sx={{ p: 2, textAlign: 'center' }}>
            <TimelineIcon sx={{ fontSize: 40, color: 'warning.main', mb: 1 }} />
            <Typography variant="h4" color="warning.main">
              {stats.failed_count.toLocaleString()}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              失败次数
            </Typography>
          </Paper>
        </Grid>
      </Grid>
    );
  };

  const renderTrendsChart = () => {
    if (!stats) return null;

    // 显示任务类型分布图表
    const typeBreakdown = stats.type_breakdown || {};
    const chartData = Object.entries(typeBreakdown).map(([type, count]) => ({
      type,
      count: count as number
    }));

    if (chartData.length === 0) {
      return (
        <Alert severity="info" sx={{ mt: 2 }}>
          暂无任务类型分布数据
        </Alert>
      );
    }

    return (
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              任务类型分布
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="type" />
                <YAxis />
                <RechartsTooltip />
                <Bar dataKey="count" fill="#2196f3" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>
      </Grid>
    );
  };

  const renderTopJobsTable = () => {
    if (!stats || !stats.type_breakdown) return null;

    const typeBreakdown = stats.type_breakdown;
    const sortedTypes = Object.entries(typeBreakdown)
      .sort(([,a], [,b]) => (b as number) - (a as number))
      .slice(0, 5);

    if (sortedTypes.length === 0) {
      return (
        <Alert severity="info" sx={{ mt: 2 }}>
          暂无任务类型数据
        </Alert>
      );
    }

    return (
      <Paper sx={{ mt: 3 }}>
        <Box sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>
            最活跃的任务类型 (Top {sortedTypes.length})
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>排名</TableCell>
                  <TableCell>任务类型</TableCell>
                  <TableCell align="right">执行次数</TableCell>
                  <TableCell align="right">占比</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {sortedTypes.map(([type, count], index) => {
                  const percentage = (count as number) / stats.total_executions * 100;
                  return (
                    <TableRow key={type}>
                      <TableCell>
                        <Chip
                          label={`#${index + 1}`}
                          size="small"
                          color={index < 3 ? 'primary' : 'default'}
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                          {type}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                          {(count as number).toLocaleString()}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
                          <Box sx={{ minWidth: 50, mr: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={percentage}
                              sx={{ height: 6, borderRadius: 3 }}
                            />
                          </Box>
                          <Typography variant="caption">
                            {percentage.toFixed(1)}%
                          </Typography>
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </Paper>
    );
  };

  const renderContent = () => {
    if (loading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      );
    }

    if (error) {
      return (
        <Alert severity="error">
          加载执行统计失败
        </Alert>
      );
    }

    if (!stats) {
      return (
        <Alert severity="info">
          暂无执行统计数据
        </Alert>
      );
    }

    return (
      <Box>
        {viewMode === 'overview' && (
          <>
            {renderOverviewCards()}
            {renderTopJobsTable()}
          </>
        )}
        {viewMode === 'trends' && renderTrendsChart()}
        {viewMode === 'details' && (
          <>
            {renderOverviewCards()}
            {renderTrendsChart()}
            {renderTopJobsTable()}
          </>
        )}
      </Box>
    );
  };

  return (
    <Card>
      <CardHeader
        avatar={<StatsIcon color="primary" />}
        title="执行统计"
        subheader={`执行情况分析 - ${timeRange === '7d' ? '最近7天' : timeRange === '30d' ? '最近30天' : '最近90天'}`}
        action={
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>时间范围</InputLabel>
              <Select
                value={timeRange}
                label="时间范围"
                onChange={(e) => handleTimeRangeChange(e.target.value as '7d' | '30d' | '90d')}
              >
                <MenuItem value="7d">最近7天</MenuItem>
                <MenuItem value="30d">最近30天</MenuItem>
                <MenuItem value="90d">最近90天</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 100 }}>
              <InputLabel>视图</InputLabel>
              <Select
                value={viewMode}
                label="视图"
                onChange={(e) => setViewMode(e.target.value as 'overview' | 'trends' | 'details')}
              >
                <MenuItem value="overview">概览</MenuItem>
                <MenuItem value="trends">类型分布</MenuItem>
                <MenuItem value="details">详细</MenuItem>
              </Select>
            </FormControl>
            <IconButton onClick={loadStats} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </Box>
        }
      />
      <CardContent>
        {renderContent()}
      </CardContent>
    </Card>
  );
};

export default ExecutionStatsPanel;
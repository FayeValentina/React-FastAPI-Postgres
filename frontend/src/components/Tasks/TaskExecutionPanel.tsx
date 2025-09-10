import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  CircularProgress,
  Alert,
} from '@mui/material';
import { useApiStore } from '../../stores/api-store';
import { TaskConfig, TaskExecution, ExecutionStats } from '../../types/task';

interface TaskExecutionPanelProps {
  configs: TaskConfig[];
}

const TaskExecutionPanel: React.FC<TaskExecutionPanelProps> = ({ configs }) => {
  const { fetchData, getApiState } = useApiStore();
  const [executions, setExecutions] = useState<TaskExecution[]>([]);
  const [stats, setStats] = useState<ExecutionStats | null>(null);
  const [filter, setFilter] = useState({
    configId: '',
    days: 7,
  });
  
  const executionsUrl = filter.configId 
    ? `/v1/tasks/executions/configs/${filter.configId}`
    : '/v1/tasks/executions/recent';
  const statsUrl = '/v1/tasks/executions/stats';
  
  const { loading } = getApiState(executionsUrl);

  const loadExecutions = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (!filter.configId) {
        params.append('hours', String(filter.days * 24));
      }
      params.append('limit', '50');
      
      const url = `${executionsUrl}?${params.toString()}`;
      const [executionsData, statsData] = await Promise.all([
        fetchData<{ executions: TaskExecution[] }>(url),
        fetchData<ExecutionStats>(`${statsUrl}?days=${filter.days}`),
      ]);
      
      setExecutions(executionsData.executions || []);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load executions:', error);
    }
  }, [fetchData, executionsUrl, statsUrl, filter.configId, filter.days]);

  useEffect(() => {
    loadExecutions();
  }, [loadExecutions]);

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* 统计信息 */}
      {stats && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>执行统计 (最近{filter.days}天)</Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 2 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">总执行次数</Typography>
                <Typography variant="h4">{stats.total_executions}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">成功率</Typography>
                <Typography variant="h4" color="success.main">{stats.success_rate.toFixed(1)}%</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">失败率</Typography>
                <Typography variant="h4" color="error.main">{stats.failure_rate.toFixed(1)}%</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">平均耗时</Typography>
                <Typography variant="h4">{formatDuration(stats.avg_duration_seconds)}</Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* 过滤器 */}
      <Box sx={{ mb: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ flex: 1, minWidth: { xs: 140, sm: 200 } }}>
          <InputLabel>配置筛选</InputLabel>
          <Select
            value={filter.configId}
            onChange={(e) => setFilter({ ...filter, configId: e.target.value })}
            label="配置筛选"
          >
            <MenuItem value="">全部</MenuItem>
            {configs.map(config => (
              <MenuItem key={config.id} value={config.id}>{config.name}</MenuItem>
            ))}
          </Select>
        </FormControl>
        
        <FormControl size="small" sx={{ flex: 1, minWidth: { xs: 120, sm: 140 } }}>
          <InputLabel>时间范围</InputLabel>
          <Select
            value={filter.days}
            onChange={(e) => setFilter({ ...filter, days: Number(e.target.value) })}
            label="时间范围"
          >
            <MenuItem value={1}>最近1天</MenuItem>
            <MenuItem value={7}>最近7天</MenuItem>
            <MenuItem value={30}>最近30天</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {/* 执行记录表格 */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>任务ID</TableCell>
              <TableCell>配置名称</TableCell>
              <TableCell>任务类型</TableCell>
              <TableCell>状态</TableCell>
              <TableCell>开始时间</TableCell>
              <TableCell>耗时</TableCell>
              <TableCell>错误信息</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {executions.map((execution) => (
              <TableRow key={execution.id}>
                <TableCell>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                    {execution.task_id.substring(0, 8)}...
                  </Typography>
                </TableCell>
                <TableCell>{execution.config_name || '-'}</TableCell>
                <TableCell>{execution.task_type || '-'}</TableCell>
                <TableCell>
                  <Chip
                    label={execution.is_success ? '成功' : '失败'}
                    color={execution.is_success ? 'success' : 'error'}
                    size="small"
                  />
                </TableCell>
                <TableCell>{new Date(execution.started_at).toLocaleString('zh-CN')}</TableCell>
                <TableCell>{formatDuration(execution.duration_seconds)}</TableCell>
                <TableCell>
                  {execution.error_message && (
                    <Typography variant="caption" color="error">
                      {execution.error_message.substring(0, 50)}...
                    </Typography>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      
      {executions.length === 0 && (
        <Alert severity="info" sx={{ mt: 2 }}>
          暂无执行记录
        </Alert>
      )}
    </Box>
  );
};

export default TaskExecutionPanel;

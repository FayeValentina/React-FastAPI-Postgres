import React, { useEffect, useState, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Alert,
  IconButton,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Close as CloseIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  HourglassEmpty as RunningIcon,
  Timelapse as TimeoutIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { TaskExecutionResponse, JobStatsResponse } from '../../types/task';

interface TaskHistoryDialogProps {
  open: boolean;
  jobId: string | null;
  jobName: string;
  onClose: () => void;
}

const TaskHistoryDialog: React.FC<TaskHistoryDialogProps> = ({
  open,
  jobId,
  jobName,
  onClose,
}) => {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));
  const { fetchData, getApiState } = useApiStore();
  
  const [executions, setExecutions] = useState<TaskExecutionResponse[]>([]);
  const [stats, setStats] = useState<JobStatsResponse | null>(null);

  const historyUrl = jobId ? `/v1/tasks/${jobId}/history` : '';
  const statsUrl = jobId ? `/v1/tasks/${jobId}/stats` : '';
  
  const { loading: historyLoading, error: historyError } = getApiState(historyUrl);
  const { loading: statsLoading } = getApiState(statsUrl);

  useEffect(() => {
    if (open && jobId) {
      loadData();
    }
  }, [open, jobId, loadData]);

  const loadData = useCallback(async () => {
    if (!jobId) return;
    
    try {
      const [historyData, statsData] = await Promise.all([
        fetchData<TaskExecutionResponse[]>(historyUrl),
        fetchData<JobStatsResponse>(statsUrl),
      ]);
      
      setExecutions(historyData || []);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load task history:', error);
    }
  }, [jobId, historyUrl, statsUrl, fetchData]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success': return <SuccessIcon color="success" />;
      case 'failed': return <ErrorIcon color="error" />;
      case 'timeout': return <TimeoutIcon color="warning" />;
      case 'running': return <RunningIcon color="primary" />;
      default: return null;
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      fullScreen={fullScreen}
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">
          任务执行历史 - {jobName}
        </Typography>
        <IconButton onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        {/* Statistics Summary */}
        {stats && !statsLoading && (
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom>
              执行统计
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 2 }}>
              <Box>
                <Typography variant="caption" color="text.secondary">总执行次数</Typography>
                <Typography variant="h6">{stats.total_runs}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">成功次数</Typography>
                <Typography variant="h6" color="success.main">{stats.successful_runs}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">失败次数</Typography>
                <Typography variant="h6" color="error.main">{stats.failed_runs}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">成功率</Typography>
                <Typography variant="h6">{stats.success_rate.toFixed(1)}%</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">平均耗时</Typography>
                <Typography variant="h6">{formatDuration(stats.avg_duration_seconds)}</Typography>
              </Box>
            </Box>
          </Paper>
        )}

        {/* Execution History Table */}
        {historyLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : historyError ? (
          <Alert severity="error">
            加载执行历史失败
          </Alert>
        ) : executions.length === 0 ? (
          <Alert severity="info">
            暂无执行历史
          </Alert>
        ) : (
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>状态</TableCell>
                  <TableCell>开始时间</TableCell>
                  <TableCell>结束时间</TableCell>
                  <TableCell>耗时</TableCell>
                  <TableCell>错误信息</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {executions.map((execution) => (
                  <TableRow key={execution.id}>
                    <TableCell>
                      <Chip
                        icon={getStatusIcon(execution.status)}
                        label={execution.status}
                        size="small"
                        color={execution.status === 'success' ? 'success' : execution.status === 'failed' ? 'error' : 'default'}
                      />
                    </TableCell>
                    <TableCell>{formatDateTime(execution.started_at)}</TableCell>
                    <TableCell>{execution.completed_at ? formatDateTime(execution.completed_at) : '-'}</TableCell>
                    <TableCell>{formatDuration(execution.duration_seconds)}</TableCell>
                    <TableCell>
                      {execution.error_message && (
                        <Typography variant="caption" color="error">
                          {execution.error_message}
                        </Typography>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} variant="contained">
          关闭
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TaskHistoryDialog;
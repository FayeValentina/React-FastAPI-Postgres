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
  IconButton,
  CircularProgress,
} from '@mui/material';
import {
  History as HistoryIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { TaskConfig, ScheduleInfo, ScheduleSummary } from '../../types/task';

interface TaskSchedulePanelProps {
  configs: TaskConfig[];
}

const TaskSchedulePanel: React.FC<TaskSchedulePanelProps> = ({ configs }) => {
  const { fetchData, getApiState } = useApiStore();
  const [schedules, setSchedules] = useState<ScheduleInfo[]>([]);
  const [summary, setSummary] = useState<ScheduleSummary | null>(null);
  
  const schedulesUrl = '/v1/tasks/schedules';
  const summaryUrl = '/v1/tasks/schedules/summary';
  const { loading } = getApiState(schedulesUrl);

  const loadSchedules = useCallback(async () => {
    try {
      const [schedulesData, summaryData] = await Promise.all([
        fetchData<{ schedules: ScheduleInfo[] }>(schedulesUrl),
        fetchData<ScheduleSummary>(summaryUrl),
      ]);
      setSchedules(schedulesData.schedules || []);
      setSummary(summaryData);
    } catch (error) {
      console.error('Failed to load schedules:', error);
    }
  }, [fetchData, schedulesUrl, summaryUrl]);

  useEffect(() => {
    loadSchedules();
  }, [loadSchedules]);

  const getConfigName = (configId?: number) => {
    if (!configId) return '-';
    const config = configs.find(c => c.id === configId);
    return config?.name || `Config #${configId}`;
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
      {summary && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>调度摘要</Typography>
            <Box sx={{ display: 'flex', gap: 4 }}>
              <Box>
                <Typography variant="body2" color="text.secondary">总任务数</Typography>
                <Typography variant="h4">{summary.total_tasks}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">活跃任务</Typography>
                <Typography variant="h4" color="success.main">{summary.active_tasks}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">暂停任务</Typography>
                <Typography variant="h4" color="warning.main">{summary.paused_tasks}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">错误任务</Typography>
                <Typography variant="h4" color="error.main">{summary.error_tasks}</Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>任务名称</TableCell>
              <TableCell>配置</TableCell>
              <TableCell>触发器</TableCell>
              <TableCell>下次运行</TableCell>
              <TableCell>操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {schedules.map((schedule) => (
              <TableRow key={schedule.task_id}>
                <TableCell>{schedule.task_name}</TableCell>
                <TableCell>{getConfigName(schedule.config_id)}</TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                    {schedule.schedule}
                  </Typography>
                </TableCell>
                <TableCell>
                  {schedule.next_run ? new Date(schedule.next_run).toLocaleString('zh-CN') : '-'}
                </TableCell>
                <TableCell>
                  <IconButton size="small">
                    <HistoryIcon />
                  </IconButton>
                  <IconButton size="small">
                    <InfoIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default TaskSchedulePanel;
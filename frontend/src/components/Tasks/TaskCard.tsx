import React from 'react';
import {
  Card,
  CardContent,
  CardActions,
  Typography,
  Chip,
  Box,
  IconButton,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  PlayArrow as RunIcon,
  Pause as PauseIcon,
  Delete as DeleteIcon,
  History as HistoryIcon,
  Schedule as ScheduleIcon,
  Error as ErrorIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import { JobInfo } from '../../types/task';

interface TaskCardProps {
  task: JobInfo;
  onRun: (task: JobInfo) => void;
  onPause: (task: JobInfo) => void;
  onResume: (task: JobInfo) => void;
  onDelete: (task: JobInfo) => void;
  onViewHistory: (task: JobInfo) => void;
  disabled?: boolean;
}

const TaskCard: React.FC<TaskCardProps> = ({
  task,
  onRun,
  onPause,
  onResume,
  onDelete,
  onViewHistory,
  disabled = false,
}) => {
  const getStatusColor = (status: string) => {
    const statusColorMap: Record<string, any> = {
      running: 'primary',
      scheduled: 'info',
      paused: 'warning',
      stopped: 'default',
      failed: 'error',
      idle: 'default',
      timeout: 'error',
      misfired: 'warning',
    };
    return statusColorMap[status] || 'default';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <RunIcon />;
      case 'scheduled': return <ScheduleIcon />;
      case 'failed': return <ErrorIcon />;
      case 'idle':
      case 'paused': return <PauseIcon />;
      default: return null;
    }
  };

  const formatNextRunTime = (time: string | null) => {
    if (!time) return '未安排';
    return new Date(time).toLocaleString('zh-CN');
  };

  const isPaused = task.status === 'paused';
  const isRunning = task.status === 'running';

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Typography variant="h6" component="h2" gutterBottom>
            {task.name}
          </Typography>
          <Chip
            label={task.status}
            color={getStatusColor(task.status)}
            size="small"
            icon={getStatusIcon(task.status)}
          />
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          ID: {task.id}
        </Typography>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          触发器: {task.trigger}
        </Typography>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          下次运行: {formatNextRunTime(task.next_run_time)}
        </Typography>

        {task.func && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            函数: {task.func}
          </Typography>
        )}

        {isRunning && (
          <LinearProgress sx={{ mt: 2 }} />
        )}
      </CardContent>

      <CardActions sx={{ justifyContent: 'space-between' }}>
        <Box>
          <Tooltip title="查看执行历史">
            <IconButton
              onClick={() => onViewHistory(task)}
              disabled={disabled}
              size="small"
            >
              <HistoryIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Box>
          {!isRunning && (
            <Tooltip title="立即执行">
              <IconButton
                onClick={() => onRun(task)}
                disabled={disabled}
                color="primary"
                size="small"
              >
                <RunIcon />
              </IconButton>
            </Tooltip>
          )}
          
          {isPaused ? (
            <Tooltip title="恢复任务">
              <IconButton
                onClick={() => onResume(task)}
                disabled={disabled}
                color="success"
                size="small"
              >
                <SuccessIcon />
              </IconButton>
            </Tooltip>
          ) : (
            <Tooltip title="暂停任务">
              <IconButton
                onClick={() => onPause(task)}
                disabled={disabled || isRunning}
                color="warning"
                size="small"
              >
                <PauseIcon />
              </IconButton>
            </Tooltip>
          )}
          
          <Tooltip title="删除任务">
            <IconButton
              onClick={() => onDelete(task)}
              disabled={disabled || isRunning}
              color="error"
              size="small"
            >
              <DeleteIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </CardActions>
    </Card>
  );
};

export default TaskCard;
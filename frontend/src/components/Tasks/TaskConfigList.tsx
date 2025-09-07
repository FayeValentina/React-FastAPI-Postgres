import React from 'react';
import {
  Grid,
  Card,
  CardContent,
  CardActions,
  Typography,
  Chip,
  Box,
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
  PlayCircle as ResumeIcon,
} from '@mui/icons-material';
import { TaskConfig } from '../../types/task';

interface TaskConfigListProps {
  configs: TaskConfig[];
  loading: boolean;
  onEdit: (config: TaskConfig) => void;
  onDelete: (config: TaskConfig) => void;
  onScheduleAction: (configId: number, action: string) => void;
}

const TaskConfigList: React.FC<TaskConfigListProps> = ({
  configs,
  loading,
  onEdit,
  onDelete,
  onScheduleAction,
}) => {
  const getSchedulerTypeColor = (type: string): 'default' | 'primary' | 'secondary' | 'warning' => {
    switch (type) {
      case 'manual': return 'default';
      case 'cron': return 'secondary';
      case 'date': return 'warning';
      default: return 'default';
    }
  };

  const getStatusColor = (status?: string): 'default' | 'success' | 'warning' | 'error' => {
    switch (status) {
      case 'active': return 'success';
      case 'paused': return 'warning';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (configs.length === 0) {
    return (
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography variant="h6" color="text.secondary">
          暂无任务配置
        </Typography>
      </Box>
    );
  }

  return (
    <Grid container spacing={3}>
      {configs.map((config) => (
        <Grid item xs={12} sm={6} md={4} key={config.id}>
          <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flexGrow: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                <Typography variant="h6" component="h2">
                  {config.name}
                </Typography>
                {config.is_scheduled && (
                  <Chip
                    label={config.schedule_status || 'scheduled'}
                    color={getStatusColor(config.schedule_status)}
                    size="small"
                  />
                )}
              </Box>

              {config.description && (
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {config.description}
                </Typography>
              )}

              <Box sx={{ mb: 2 }}>
                <Chip
                  label={`类型: ${config.task_type}`}
                  size="small"
                  sx={{ mr: 1 }}
                />
                <Chip
                  label={config.scheduler_type}
                  color={getSchedulerTypeColor(config.scheduler_type)}
                  size="small"
                />
              </Box>

              <Typography variant="caption" display="block" color="text.secondary">
                优先级: {config.priority} | 重试: {config.max_retries}次
              </Typography>
              <Typography variant="caption" display="block" color="text.secondary">
                创建于: {new Date(config.created_at).toLocaleDateString('zh-CN')}
              </Typography>
            </CardContent>

            <CardActions>
              {config.is_scheduled ? (
                <>
                  <Tooltip title="停止调度">
                    <IconButton
                      size="small"
                      onClick={() => onScheduleAction(config.id, 'stop')}
                    >
                      <StopIcon />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="暂停调度">
                    <IconButton
                      size="small"
                      onClick={() => onScheduleAction(config.id, 'pause')}
                    >
                      <PauseIcon />
                    </IconButton>
                  </Tooltip>
                </>
              ) : (
                <Tooltip title="启动调度">
                  <IconButton
                    size="small"
                    color="primary"
                    onClick={() => onScheduleAction(config.id, 'start')}
                  >
                    <StartIcon />
                  </IconButton>
                </Tooltip>
              )}
              
              {config.schedule_status === 'paused' && (
                <Tooltip title="恢复调度">
                  <IconButton
                    size="small"
                    color="success"
                    onClick={() => onScheduleAction(config.id, 'resume')}
                  >
                    <ResumeIcon />
                  </IconButton>
                </Tooltip>
              )}

              <Box sx={{ ml: 'auto' }}>
                <Tooltip title="编辑">
                  <IconButton
                    size="small"
                    onClick={() => onEdit(config)}
                  >
                    <EditIcon />
                  </IconButton>
                </Tooltip>
                <Tooltip title="删除">
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => onDelete(config)}
                  >
                    <DeleteIcon />
                  </IconButton>
                </Tooltip>
              </Box>
            </CardActions>
          </Card>
        </Grid>
      ))}
    </Grid>
  );
};

export default TaskConfigList;

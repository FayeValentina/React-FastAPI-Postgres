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
} from '@mui/icons-material';
import { TaskConfig } from '../../types/task';

interface TaskConfigListProps {
  configs: TaskConfig[];
  loading: boolean;
  onEdit: (config: TaskConfig) => void;
  onDelete: (config: TaskConfig) => void;
  scheduleCounts?: Record<number, { active: number; paused: number }>;
}

const TaskConfigList: React.FC<TaskConfigListProps> = ({
  configs,
  loading,
  onEdit,
  onDelete,
  scheduleCounts = {},
}) => {
  const getSchedulerTypeColor = (type: string): 'default' | 'primary' | 'secondary' | 'warning' => {
    switch (type) {
      case 'manual': return 'default';
      case 'cron': return 'secondary';
      case 'date': return 'warning';
      default: return 'default';
    }
  };

  // config与schedule完全解耦，移除状态颜色计算

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
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2, gap: 1, flexWrap: 'wrap' }}>
                <Typography variant="h6" component="h2">
                  {config.name}
                </Typography>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  <Chip label={`活跃: ${scheduleCounts[config.id]?.active ?? 0}`} color="success" size="small" />
                  <Chip label={`暂停: ${scheduleCounts[config.id]?.paused ?? 0}`} color={(scheduleCounts[config.id]?.paused ?? 0) > 0 ? 'warning' : 'default'} size="small" />
                </Box>
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

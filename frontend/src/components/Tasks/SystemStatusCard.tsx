import React from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Box,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  Circle as CircleIcon,
  Schedule as ScheduleIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import { SystemStatus } from '../../types/task';

interface SystemStatusCardProps {
  status: SystemStatus | null;
}

const SystemStatusCard: React.FC<SystemStatusCardProps> = ({ status }) => {
  if (!status) return null;

  return (
    <Card>
      <CardHeader
        title="系统状态"
        subheader={new Date(status.system_time).toLocaleString('zh-CN')}
      />
      <CardContent>
        <List>
          <ListItem>
            <ListItemIcon>
              <ScheduleIcon />
            </ListItemIcon>
            <ListItemText
              primary="调度器状态"
              secondary={
                <Chip
                  label={status.scheduler_status}
                  color={status.scheduler_status === '运行中' ? 'success' : 'default'}
                  size="small"
                />
              }
            />
          </ListItem>
          
          <ListItem>
            <ListItemIcon>
              <StorageIcon />
            </ListItemIcon>
            <ListItemText
              primary="数据库状态"
              secondary={
                <Chip
                  label={status.database_status}
                  color={status.database_status === '正常' ? 'success' : 'error'}
                  size="small"
                />
              }
            />
          </ListItem>
          
          <ListItem>
            <ListItemIcon>
              <CircleIcon />
            </ListItemIcon>
            <ListItemText
              primary="Redis状态"
              secondary={
                <Chip
                  label={status.redis_status}
                  color={status.redis_status === '正常' ? 'success' : 'error'}
                  size="small"
                />
              }
            />
          </ListItem>
        </List>

        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2" gutterBottom>任务类型分布</Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {Object.entries(status.config_stats.by_type).map(([type, count]) => (
              <Chip
                key={type}
                label={`${type}: ${count}`}
                size="small"
                variant="outlined"
              />
            ))}
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default SystemStatusCard;
import React from 'react';
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
import { SystemHealth } from '../../types/task';

interface SystemHealthPanelProps {
  health?: SystemHealth | null;
}

const SystemHealthPanel: React.FC<SystemHealthPanelProps> = ({ health }) => {
  if (!health) {
    return (
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </CardContent>
      </Card>
    );
  }

  // Map health status to score for display
  const getHealthScore = (status: string) => {
    switch (status) {
      case 'healthy': return 1.0;
      case 'degraded': return 0.6;
      case 'unhealthy': return 0.2;
      default: return 0;
    }
  };

  const healthScore = getHealthScore(health.status);
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
          <Box>
            <Typography variant="caption" color="text.secondary">系统状态</Typography>
            <Typography variant="body1">
              <Chip
                label={health.status.toUpperCase()}
                color={healthColor}
                size="small"
              />
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">检查时间</Typography>
            <Typography variant="body2">
              {new Date(health.timestamp).toLocaleString('zh-CN')}
            </Typography>
          </Box>
        </Box>

        {Object.keys(health.components).length > 0 && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              组件状态
            </Typography>
            {Object.entries(health.components).map(([name, component]) => (
              <Alert 
                key={name}
                severity={component.status === 'healthy' ? 'success' : 'warning'}
                sx={{ mb: 1 }}
              >
                <Typography variant="body2">
                  <strong>{name}:</strong> {component.message}
                </Typography>
              </Alert>
            ))}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default SystemHealthPanel;
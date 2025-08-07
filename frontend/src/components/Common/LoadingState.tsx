import React from 'react';
import {
  Box,
  CircularProgress,
  Typography,
  Skeleton,
  Card,
  CardContent,
  Grid,
} from '@mui/material';

interface LoadingStateProps {
  type?: 'spinner' | 'skeleton' | 'card';
  message?: string;
  size?: 'small' | 'medium' | 'large';
  count?: number; // 用于skeleton类型
}

const LoadingState: React.FC<LoadingStateProps> = ({
  type = 'spinner',
  message = '加载中...',
  size = 'medium',
  count = 3,
}) => {
  const getSize = () => {
    switch (size) {
      case 'small': return 24;
      case 'large': return 60;
      default: return 40;
    }
  };

  if (type === 'spinner') {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          py: 4,
          gap: 2,
        }}
      >
        <CircularProgress size={getSize()} />
        {message && (
          <Typography variant="body2" color="text.secondary">
            {message}
          </Typography>
        )}
      </Box>
    );
  }

  if (type === 'skeleton') {
    return (
      <Box>
        {Array.from({ length: count }).map((_, index) => (
          <Box key={index} sx={{ mb: 2 }}>
            <Skeleton variant="text" width="60%" height={24} />
            <Skeleton variant="text" width="80%" height={16} />
            <Skeleton variant="rectangular" width="100%" height={48} sx={{ mt: 1 }} />
          </Box>
        ))}
      </Box>
    );
  }

  if (type === 'card') {
    return (
      <Grid container spacing={2}>
        {Array.from({ length: count }).map((_, index) => (
          <Grid item xs={12} sm={6} md={4} key={index}>
            <Card>
              <CardContent>
                <Skeleton variant="text" width="70%" height={32} />
                <Skeleton variant="text" width="90%" height={16} sx={{ mt: 1 }} />
                <Skeleton variant="text" width="60%" height={16} />
                <Skeleton variant="rectangular" width="100%" height={120} sx={{ mt: 2 }} />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    );
  }

  return null;
};

export default LoadingState;
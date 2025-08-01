import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Grid,
  Box,
  Chip,
  CircularProgress,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  Schedule as ScheduleIcon,
  Assessment as AssessmentIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { ScrapeSessionStats } from '../../types/session';

const SessionStatsPanel: React.FC = () => {
  const { fetchData, getApiState } = useApiStore();
  const [stats, setStats] = useState<ScrapeSessionStats | null>(null);

  const statsApiUrl = '/v1/scraping/scrape-sessions/stats';
  const { loading, error } = getApiState(statsApiUrl);

  useEffect(() => {
    let isMounted = true;
    
    const loadStats = async () => {
      try {
        const data = await fetchData<ScrapeSessionStats>(statsApiUrl);
        if (isMounted) {
          setStats(data);
        }
      } catch (error) {
        if (isMounted) {
          console.error('Failed to load session stats:', error);
        }
      }
    };

    loadStats();
    
    return () => {
      isMounted = false;
    };
  }, [fetchData, statsApiUrl]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !stats) {
    return null;
  }

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('zh-CN').format(num);
  };

  const formatDuration = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else {
      return `${minutes}m`;
    }
  };

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AssessmentIcon />
          统计概览 (最近 {stats.period_days} 天)
        </Typography>
        
        <Grid container spacing={3}>
          <Grid item xs={12} sm={6} md={3}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h4" color="primary">
                {formatNumber(stats.total_sessions)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                总会话数
              </Typography>
            </Box>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Box sx={{ textAlign: 'center' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
                <Typography variant="h4" color="success.main">
                  {stats.success_rate.toFixed(1)}%
                </Typography>
                <SuccessIcon color="success" />
              </Box>
              <Typography variant="body2" color="text.secondary">
                成功率
              </Typography>
              <Typography variant="caption" color="text.secondary">
                ({formatNumber(stats.successful_sessions)}/{formatNumber(stats.total_sessions)})
              </Typography>
            </Box>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Box sx={{ textAlign: 'center' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
                <Typography variant="h4" color="info.main">
                  {formatDuration(stats.avg_duration_seconds)}
                </Typography>
                <ScheduleIcon color="action" />
              </Box>
              <Typography variant="body2" color="text.secondary">
                平均时长
              </Typography>
            </Box>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="h4" color="secondary">
                {formatNumber(stats.total_comments_found)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                总评论数
              </Typography>
              <Typography variant="caption" color="text.secondary">
                质量评论: {formatNumber(stats.quality_comments_found)}
              </Typography>
            </Box>
          </Grid>
        </Grid>

        <Box sx={{ mt: 2, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Chip
            icon={<TrendingUpIcon />}
            label={`帖子: ${formatNumber(stats.total_posts_found)}`}
            variant="outlined"
            size="small"
          />
          <Chip
            label={`已发布: ${formatNumber(stats.total_published)}`}
            variant="outlined"
            size="small"
          />
        </Box>
      </CardContent>
    </Card>
  );
};

export default SessionStatsPanel;
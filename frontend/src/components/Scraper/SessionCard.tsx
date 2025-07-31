import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Chip,
  Box,
  LinearProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  PlayArrow as RunningIcon,
  CheckCircle as CompletedIcon,
  Error as ErrorIcon,
  Schedule as PendingIcon,
  Visibility as ViewIcon,
} from '@mui/icons-material';
import { ScrapeSessionResponse } from '../../types/session';

interface SessionCardProps {
  session: ScrapeSessionResponse;
  onClick: () => void;
}

const SessionCard: React.FC<SessionCardProps> = ({ session, onClick }) => {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'primary';
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'pending': return 'default';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <RunningIcon />;
      case 'completed': return <CompletedIcon />;
      case 'failed': return <ErrorIcon />;
      case 'pending': return <PendingIcon />;
      default: return <PendingIcon />;
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`;
    } else {
      return `${secs}s`;
    }
  };

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('zh-CN');
  };

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', cursor: 'pointer' }} onClick={onClick}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Typography variant="h6" component="h2" gutterBottom>
            会话 #{session.id}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chip
              label={session.status}
              color={getStatusColor(session.status)}
              size="small"
              icon={getStatusIcon(session.status)}
            />
            <Tooltip title="查看详情">
              <IconButton size="small">
                <ViewIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          类型: {session.session_type}
        </Typography>

        {session.bot_config_name && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            配置: {session.bot_config_name}
          </Typography>
        )}

        {session.user_username && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            用户: {session.user_username}
          </Typography>
        )}

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          开始时间: {formatDateTime(session.started_at)}
        </Typography>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          结束时间: {formatDateTime(session.completed_at)}
        </Typography>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          持续时间: {formatDuration(session.duration_seconds)}
        </Typography>

        {session.status === 'running' && (
          <LinearProgress sx={{ mb: 2 }} />
        )}

        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, mb: 2 }}>
          <Typography variant="caption">
            帖子: {session.total_posts_found}
          </Typography>
          <Typography variant="caption">
            评论: {session.total_comments_found}
          </Typography>
          <Typography variant="caption">
            质量评论: {session.quality_comments_count}
          </Typography>
          <Typography variant="caption">
            已发布: {session.published_count}
          </Typography>
        </Box>

        {session.error_message && (
          <Typography variant="caption" color="error" sx={{ display: 'block' }}>
            错误: {session.error_message.substring(0, 50)}...
          </Typography>
        )}

        <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 1 }}>
          创建于: {formatDateTime(session.created_at)}
        </Typography>
      </CardContent>
    </Card>
  );
};

export default SessionCard;
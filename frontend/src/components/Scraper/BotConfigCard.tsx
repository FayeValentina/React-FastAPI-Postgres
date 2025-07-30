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
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
} from '@mui/icons-material';
import { BotConfigResponse } from '../../types/bot';

interface BotConfigCardProps {
  config: BotConfigResponse;
  onEdit: (config: BotConfigResponse) => void;
  onDelete: (config: BotConfigResponse) => void;
  onToggle: (config: BotConfigResponse) => void;
  onTriggerScraping?: (config: BotConfigResponse) => void;
  loading?: boolean;
}

const BotConfigCard: React.FC<BotConfigCardProps> = ({
  config,
  onEdit,
  onDelete,
  onToggle,
  onTriggerScraping,
  loading = false,
}) => {
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Typography variant="h6" component="h2" gutterBottom>
            {config.name}
          </Typography>
          <Chip
            label={config.is_active ? '运行中' : '已停止'}
            color={config.is_active ? 'success' : 'default'}
            size="small"
            icon={config.is_active ? <PlayIcon /> : <StopIcon />}
          />
        </Box>

        {config.description && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {config.description}
          </Typography>
        )}

        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" display="block" gutterBottom>
            目标Subreddits ({config.target_subreddits.length}个):
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {config.target_subreddits.slice(0, 3).map((subreddit) => (
              <Chip
                key={subreddit}
                label={`r/${subreddit}`}
                size="small"
                variant="outlined"
              />
            ))}
            {config.target_subreddits.length > 3 && (
              <Chip
                label={`+${config.target_subreddits.length - 3}个`}
                size="small"
                variant="outlined"
              />
            )}
          </Box>
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, mb: 2 }}>
          <Typography variant="caption">
            帖子数量: {config.posts_per_subreddit}
          </Typography>
          <Typography variant="caption">
            评论数量: {config.comments_per_post}
          </Typography>
          <Typography variant="caption">
            排序方式: {config.sort_method}
          </Typography>
          <Typography variant="caption">
            时间筛选: {config.time_filter}
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
          {config.enable_ai_filter && (
            <Chip label="AI过滤" size="small" color="primary" />
          )}
          {config.auto_publish_enabled && (
            <Chip label="自动发布" size="small" color="secondary" />
          )}
        </Box>

        <Typography variant="caption" display="block" color="text.secondary">
          创建于: {formatDate(config.created_at)}
        </Typography>
        <Typography variant="caption" display="block" color="text.secondary">
          更新于: {formatDate(config.updated_at)}
        </Typography>
      </CardContent>

      <CardActions sx={{ justifyContent: 'space-between', px: 2, pb: 2 }}>
        <Box>
          <FormControlLabel
            control={
              <Switch
                checked={config.is_active}
                onChange={() => onToggle(config)}
                disabled={loading}
                size="small"
              />
            }
            label={config.is_active ? '启用' : '禁用'}
            sx={{ mr: 1 }}
          />
        </Box>

        <Box>
          {onTriggerScraping && config.is_active && (
            <Tooltip title="手动触发爬取">
              <IconButton
                onClick={() => onTriggerScraping(config)}
                disabled={loading}
                color="primary"
              >
                <PlayIcon />
              </IconButton>
            </Tooltip>
          )}
          
          <Tooltip title="编辑配置">
            <IconButton
              onClick={() => onEdit(config)}
              disabled={loading}
              color="primary"
            >
              <EditIcon />
            </IconButton>
          </Tooltip>
          
          <Tooltip title="删除配置">
            <IconButton
              onClick={() => onDelete(config)}
              disabled={loading}
              color="error"
            >
              <DeleteIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </CardActions>
    </Card>
  );
};

export default BotConfigCard;
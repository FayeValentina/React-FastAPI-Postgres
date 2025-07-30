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
  Checkbox,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';
import { BotConfigResponse } from '../../types/bot';

interface BotConfigCardProps {
  config: BotConfigResponse;
  onEdit: (config: BotConfigResponse) => void;
  onDelete: (config: BotConfigResponse) => void;
  onToggle: (config: BotConfigResponse) => void;
  onToggleAutoScrape?: (config: BotConfigResponse) => void;
  onTriggerScraping?: (config: BotConfigResponse) => void;
  loading?: boolean;
  // 多选相关
  selectable?: boolean;
  selected?: boolean;
  onSelect?: (config: BotConfigResponse, selected: boolean) => void;
}

const BotConfigCard: React.FC<BotConfigCardProps> = ({
  config,
  onEdit,
  onDelete,
  onToggle,
  onToggleAutoScrape,
  onTriggerScraping,
  loading = false,
  selectable = false,
  selected = false,
  onSelect,
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

  const handleSelectChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (onSelect) {
      onSelect(config, event.target.checked);
    }
  };

  return (
    <Card sx={{ 
      height: '100%', 
      display: 'flex', 
      flexDirection: 'column',
      border: selected ? '2px solid' : '1px solid',
      borderColor: selected ? 'primary.main' : 'divider',
      bgcolor: selected ? 'action.selected' : 'background.paper'
    }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexGrow: 1 }}>
            {selectable && (
              <Checkbox
                checked={selected}
                onChange={handleSelectChange}
                size="small"
                sx={{ mt: -0.5 }}
              />
            )}
            <Typography variant="h6" component="h2" gutterBottom sx={{ flexGrow: 1, mt: selectable ? 0.5 : 0 }}>
              {config.name}
            </Typography>
          </Box>
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
          <Chip 
            label={config.auto_scrape_enabled ? "定时爬取已启用" : "定时爬取已禁用"} 
            size="small" 
            color={config.auto_scrape_enabled ? "secondary" : "default"}
            icon={config.auto_scrape_enabled ? <ScheduleIcon /> : undefined}
          />
        </Box>

        <Typography variant="caption" display="block" color="text.secondary">
          创建于: {formatDate(config.created_at)}
        </Typography>
        <Typography variant="caption" display="block" color="text.secondary">
          更新于: {formatDate(config.updated_at)}
        </Typography>
      </CardContent>

      <CardActions sx={{ justifyContent: 'space-between', px: 2, pb: 2 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
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
          {onToggleAutoScrape && (
            <FormControlLabel
              control={
                <Switch
                  checked={config.auto_scrape_enabled}
                  onChange={() => onToggleAutoScrape(config)}
                  disabled={loading}
                  size="small"
                />
              }
              label={config.auto_scrape_enabled ? '自动化' : '手动'}
              sx={{ mr: 1 }}
            />
          )}
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
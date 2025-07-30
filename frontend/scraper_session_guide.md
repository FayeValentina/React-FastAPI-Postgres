# 爬虫会话管理功能实现指南

## 功能概述

基于现有的 `scraping_routes.py` API，实现爬虫会话管理前端界面。会话在系统中作为爬虫的爬取履历，用户可以查看每个爬取会话的状态、时间、结果等信息。

## 功能需求

### 主要功能
1. **会话列表视图** - 显示所有爬取会话的概览
2. **会话详情** - 查看单个会话的详细信息  
3. **统计面板** - 显示爬取会话的统计数据
4. **过滤和搜索** - 按状态、时间等过滤会话
5. **实时状态更新** - 显示正在运行的会话状态

### UI设计模式
- **Dashboard模式** - 顶部显示关键统计指标
- **Master-Detail模式** - 列表+详情模态框
- **Status indicator模式** - 清晰的状态指示器
- **Progressive disclosure模式** - 概要+详情展开
- **Real-time updates模式** - 自动刷新运行状态

## 文件结构

### 新增文件

```
frontend/src/
├── pages/
│   └── SessionManagementPage.tsx          # 会话管理主页面
├── components/Scraper/
│   ├── SessionCard.tsx                    # 会话卡片组件
│   ├── SessionDetailDialog.tsx            # 会话详情对话框
│   ├── SessionStatsPanel.tsx              # 统计面板组件
│   └── SessionFilterBar.tsx               # 过滤条件栏
├── types/
│   └── session.ts                         # 会话相关类型定义
```

### 修改文件

```
frontend/src/
├── components/Scraper/
│   ├── ScraperLayout.tsx                  # 启用会话管理菜单项
│   └── index.ts                           # 导出新组件
└── routes.tsx                             # 添加会话管理路由
```

## 类型定义

```typescript
// frontend/src/types/session.ts

export interface ScrapeSessionBase {
  session_type: string;
  status: string;
}

export interface ScrapeSessionResponse extends ScrapeSessionBase {
  id: number;
  bot_config_id: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  total_posts_found: number;
  total_comments_found: number;
  quality_comments_count: number;
  published_count: number;
  error_message: string | null;
  error_details: Record<string, any> | null;
  config_snapshot: Record<string, any> | null;
  created_at: string;
}

export interface ScrapeSessionStats {
  period_days: number;
  total_sessions: number;
  successful_sessions: number;
  success_rate: number;
  total_posts_found: number;
  total_comments_found: number;
  quality_comments_found: number;
  total_published: number;
  avg_duration_seconds: number;
}

export interface ScrapeTriggerResponse {
  session_id: number;
  status: string;
  message: string;
}

// 会话状态类型
export type SessionStatus = 'pending' | 'running' | 'completed' | 'failed';

// 会话类型
export type SessionType = 'manual' | 'scheduled' | 'auto';

// 过滤条件
export interface SessionFilters {
  status?: SessionStatus;
  session_type?: SessionType;
  date_range?: {
    start: string;
    end: string;
  };
  bot_config_id?: number;
}
```

## 组件样板代码

### 1. 会话管理主页面

```typescript
// frontend/src/pages/SessionManagementPage.tsx

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Grid,
  Alert,
  CircularProgress,
  Fab,
} from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/auth-store';
import { useApiStore } from '../stores/api-store';
import ScraperLayout from '../components/Scraper/ScraperLayout';
import SessionStatsPanel from '../components/Scraper/SessionStatsPanel';
import SessionFilterBar from '../components/Scraper/SessionFilterBar';
import SessionCard from '../components/Scraper/SessionCard';
import SessionDetailDialog from '../components/Scraper/SessionDetailDialog';
import { ScrapeSessionResponse, SessionFilters } from '../types/session';

const SessionManagementPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const { fetchData, getApiState } = useApiStore();
  
  const [sessions, setSessions] = useState<ScrapeSessionResponse[]>([]);
  const [selectedSession, setSelectedSession] = useState<ScrapeSessionResponse | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [filters, setFilters] = useState<SessionFilters>({});
  const [autoRefresh, setAutoRefresh] = useState(true);

  // API states
  const sessionsApiUrl = '/v1/scrape-sessions';
  const { loading: sessionsLoading, error: sessionsError } = getApiState(sessionsApiUrl);

  const loadSessions = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filters.status) params.append('status', filters.status);
      
      const url = `${sessionsApiUrl}${params.toString() ? `?${params.toString()}` : ''}`;
      const data = await fetchData<ScrapeSessionResponse[]>(url);
      setSessions(data || []);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  }, [fetchData, filters]);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    loadSessions();
  }, [isAuthenticated, navigate, loadSessions]);

  // Auto refresh for running sessions
  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(() => {
      const hasRunningSessions = sessions.some(session => session.status === 'running');
      if (hasRunningSessions) {
        loadSessions();
      }
    }, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, [autoRefresh, sessions, loadSessions]);

  const handleSessionClick = (session: ScrapeSessionResponse) => {
    setSelectedSession(session);
    setDetailDialogOpen(true);
  };

  const handleFilterChange = (newFilters: SessionFilters) => {
    setFilters(newFilters);
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <ScraperLayout>
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" gutterBottom>
            会话管理
          </Typography>
          <Fab
            color="primary"
            aria-label="refresh"
            onClick={loadSessions}
            disabled={sessionsLoading}
            size="small"
          >
            <RefreshIcon />
          </Fab>
        </Box>

        {/* Statistics Panel */}
        <SessionStatsPanel />

        {/* Filter Bar */}
        <SessionFilterBar 
          filters={filters}
          onFiltersChange={handleFilterChange}
          autoRefresh={autoRefresh}
          onAutoRefreshChange={setAutoRefresh}
        />

        {sessionsError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {sessionsError.message || '加载失败，请稍后重试'}
          </Alert>
        )}

        {/* Sessions Grid */}
        {sessionsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress />
          </Box>
        ) : sessions.length === 0 ? (
          <Box sx={{ textAlign: 'center', mt: 4 }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              还没有爬取会话
            </Typography>
            <Typography variant="body2" color="text.secondary">
              创建Bot配置并执行爬取后，会话记录会显示在这里
            </Typography>
          </Box>
        ) : (
          <Grid container spacing={3}>
            {sessions.map((session) => (
              <Grid item xs={12} sm={6} lg={4} key={session.id}>
                <SessionCard
                  session={session}
                  onClick={() => handleSessionClick(session)}
                />
              </Grid>
            ))}
          </Grid>
        )}

        {/* Session Detail Dialog */}
        <SessionDetailDialog
          open={detailDialogOpen}
          session={selectedSession}
          onClose={() => setDetailDialogOpen(false)}
        />
      </Box>
    </ScraperLayout>
  );
};

export default SessionManagementPage;
```

### 2. 会话卡片组件

```typescript
// frontend/src/components/Scraper/SessionCard.tsx

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
```

### 3. 统计面板组件

```typescript
// frontend/src/components/Scraper/SessionStatsPanel.tsx

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

  const statsApiUrl = '/v1/scrape-sessions/stats';
  const { loading, error } = getApiState(statsApiUrl);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const data = await fetchData<ScrapeSessionStats>(statsApiUrl);
        setStats(data);
      } catch (error) {
        console.error('Failed to load session stats:', error);
      }
    };

    loadStats();
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
```

### 4. 过滤条件栏组件

```typescript
// frontend/src/components/Scraper/SessionFilterBar.tsx

import React from 'react';
import {
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Grid,
  Chip,
  Box,
} from '@mui/material';
import {
  FilterList as FilterIcon,
  AutorenewIcon,
} from '@mui/icons-material';
import { SessionFilters, SessionStatus, SessionType } from '../../types/session';

interface SessionFilterBarProps {
  filters: SessionFilters;
  onFiltersChange: (filters: SessionFilters) => void;
  autoRefresh: boolean;
  onAutoRefreshChange: (enabled: boolean) => void;
}

const SessionFilterBar: React.FC<SessionFilterBarProps> = ({
  filters,
  onFiltersChange,
  autoRefresh,
  onAutoRefreshChange,
}) => {
  const handleStatusChange = (status: SessionStatus | '') => {
    onFiltersChange({
      ...filters,
      status: status || undefined,
    });
  };

  const handleTypeChange = (type: SessionType | '') => {
    onFiltersChange({
      ...filters,
      session_type: type || undefined,
    });
  };

  const clearFilters = () => {
    onFiltersChange({});
  };

  const hasActiveFilters = filters.status || filters.session_type;

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Grid container spacing={2} alignItems="center">
          <Grid item>
            <FilterIcon color="action" />
          </Grid>
          
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>状态</InputLabel>
              <Select
                value={filters.status || ''}
                onChange={(e) => handleStatusChange(e.target.value as SessionStatus | '')}
                label="状态"
              >
                <MenuItem value="">全部</MenuItem>
                <MenuItem value="pending">等待中</MenuItem>
                <MenuItem value="running">运行中</MenuItem>
                <MenuItem value="completed">已完成</MenuItem>
                <MenuItem value="failed">失败</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>类型</InputLabel>
              <Select
                value={filters.session_type || ''}
                onChange={(e) => handleTypeChange(e.target.value as SessionType | '')}
                label="类型"
              >
                <MenuItem value="">全部</MenuItem>
                <MenuItem value="manual">手动</MenuItem>
                <MenuItem value="scheduled">定时</MenuItem>
                <MenuItem value="auto">自动</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={autoRefresh}
                  onChange={(e) => onAutoRefreshChange(e.target.checked)}
                  icon={<AutorenewIcon />}
                  checkedIcon={<AutorenewIcon />}
                />
              }
              label="自动刷新"
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {hasActiveFilters && (
                <Chip
                  label="清除过滤"
                  onClick={clearFilters}
                  onDelete={clearFilters}
                  size="small"
                  variant="outlined"
                />
              )}
              {filters.status && (
                <Chip
                  label={`状态: ${filters.status}`}
                  size="small"
                  color="primary"
                />
              )}
              {filters.session_type && (
                <Chip
                  label={`类型: ${filters.session_type}`}
                  size="small"
                  color="secondary"
                />
              )}
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default SessionFilterBar;
```

### 5. 会话详情对话框组件

```typescript
// frontend/src/components/Scraper/SessionDetailDialog.tsx

import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Grid,
  Chip,
  Box,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  Settings as SettingsIcon,
  Error as ErrorIcon,
  Assessment as StatsIcon,
} from '@mui/icons-material';
import { ScrapeSessionResponse } from '../../types/session';

interface SessionDetailDialogProps {
  open: boolean;
  session: ScrapeSessionResponse | null;
  onClose: () => void;
}

const SessionDetailDialog: React.FC<SessionDetailDialogProps> = ({
  open,
  session,
  onClose,
}) => {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));

  if (!session) {
    return null;
  }

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('zh-CN');
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours}h ${minutes}m ${secs}s`;
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      fullScreen={fullScreen}
      scroll="paper"
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6">
            会话详情 #{session.id}
          </Typography>
          <Chip
            label={session.status}
            color={session.status === 'completed' ? 'success' : session.status === 'failed' ? 'error' : 'primary'}
            size="small"
          />
        </Box>
        <Button onClick={onClose} startIcon={<CloseIcon />}>
          关闭
        </Button>
      </DialogTitle>

      <DialogContent dividers>
        {/* Basic Information */}
        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <StatsIcon />
          基本信息
        </Typography>
        
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">会话ID</Typography>
            <Typography variant="body1">{session.id}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">Bot配置ID</Typography>
            <Typography variant="body1">{session.bot_config_id}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">会话类型</Typography>
            <Typography variant="body1">{session.session_type}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">状态</Typography>
            <Typography variant="body1">{session.status}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">开始时间</Typography>
            <Typography variant="body1">{formatDateTime(session.started_at)}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">结束时间</Typography>
            <Typography variant="body1">{formatDateTime(session.completed_at)}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">持续时间</Typography>
            <Typography variant="body1">{formatDuration(session.duration_seconds)}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">创建时间</Typography>
            <Typography variant="body1">{formatDateTime(session.created_at)}</Typography>
          </Grid>
        </Grid>

        <Divider sx={{ mb: 3 }} />

        {/* Results Statistics */}
        <Typography variant="h6" gutterBottom>
          爬取结果
        </Typography>
        
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} sm={3}>
            <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'primary.light', borderRadius: 1 }}>
              <Typography variant="h4" color="primary.contrastText">
                {session.total_posts_found}
              </Typography>
              <Typography variant="caption" color="primary.contrastText">
                总帖子数
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'secondary.light', borderRadius: 1 }}>
              <Typography variant="h4" color="secondary.contrastText">
                {session.total_comments_found}
              </Typography>
              <Typography variant="caption" color="secondary.contrastText">
                总评论数
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'success.light', borderRadius: 1 }}>
              <Typography variant="h4" color="success.contrastText">
                {session.quality_comments_count}
              </Typography>
              <Typography variant="caption" color="success.contrastText">
                质量评论
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
              <Typography variant="h4" color="info.contrastText">
                {session.published_count}
              </Typography>
              <Typography variant="caption" color="info.contrastText">
                已发布
              </Typography>
            </Box>
          </Grid>
        </Grid>

        {/* Configuration Snapshot */}
        {session.config_snapshot && (
          <Accordion sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <SettingsIcon />
                <Typography variant="h6">配置快照</Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <pre style={{ fontSize: '12px', overflow: 'auto' }}>
                {JSON.stringify(session.config_snapshot, null, 2)}
              </pre>
            </AccordionDetails>
          </Accordion>
        )}

        {/* Error Details */}
        {session.error_message && (
          <Accordion sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ErrorIcon color="error" />
                <Typography variant="h6" color="error">错误详情</Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body2" color="error" paragraph>
                <strong>错误消息:</strong> {session.error_message}
              </Typography>
              {session.error_details && (
                <pre style={{ fontSize: '12px', overflow: 'auto', color: theme.palette.error.main }}>
                  {JSON.stringify(session.error_details, null, 2)}
                </pre>
              )}
            </AccordionDetails>
          </Accordion>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} variant="contained">
          关闭
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SessionDetailDialog;
```

## 需要修改的文件

### 1. 启用菜单项

```typescript
// frontend/src/components/Scraper/ScraperLayout.tsx
// 在 menuItems 中将 sessions 的 implemented 改为 true

const menuItems = [
  {
    text: 'Bot管理',
    icon: <BotIcon />,
    path: '/scraper/bots',
    implemented: true,
  },
  {
    text: '会话管理',
    icon: <SessionIcon />,
    path: '/scraper/sessions',
    implemented: true, // 改为 true
  },
  // ... 其他项目
];
```

### 2. 添加路由

```typescript
// frontend/src/routes.tsx
// 在爬虫管理路由部分添加

import SessionManagementPage from './pages/SessionManagementPage';

// 在 Routes 中添加
<Route path="/scraper/sessions" element={
  <ProtectedRoute>
    <SessionManagementPage />
  </ProtectedRoute>
} />
```

### 3. 更新组件导出

```typescript
// frontend/src/components/Scraper/index.ts
export { default as ScraperLayout } from './ScraperLayout';
export { default as BotConfigCard } from './BotConfigCard';
export { default as BotConfigForm } from './BotConfigForm';
export { default as BotConfigDialog } from './BotConfigDialog';
export { default as SessionCard } from './SessionCard';
export { default as SessionDetailDialog } from './SessionDetailDialog';
export { default as SessionStatsPanel } from './SessionStatsPanel';
export { default as SessionFilterBar } from './SessionFilterBar';
```

## 实现步骤建议

1. **先创建类型定义** - `types/session.ts`
2. **实现基础组件** - `SessionCard.tsx`
3. **实现统计面板** - `SessionStatsPanel.tsx`
4. **实现过滤条件栏** - `SessionFilterBar.tsx`
5. **实现详情对话框** - `SessionDetailDialog.tsx`
6. **实现主页面** - `SessionManagementPage.tsx`
7. **修改路由和布局** - 启用菜单项和添加路由
8. **测试和优化** - 测试各个功能点

## 注意事项

1. **错误处理** - 妥善处理API调用失败的情况
2. **性能优化** - 大量会话时考虑分页加载
3. **用户体验** - 提供清晰的状态指示器和加载状态
4. **权限控制** - 确保用户只能查看自己的会话数据
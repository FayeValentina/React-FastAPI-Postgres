目前关于前端的重构，需要完成两个任务:
1.创建与后台定时任务系统端点相对应的页面
2.扩展原来<爬虫管理系统>，变成综合管理，爬虫只是一小部分，以后会添加更多功能(比如现在就要添加:定时任务管理)

## 1. 创建任务管理相关的类型定义

首先创建任务相关的类型定义文件：

```typescript
// frontend/src/types/task.ts
// 任务状态枚举
export type TaskStatus = 
  | 'running'
  | 'scheduled'
  | 'paused'
  | 'stopped'
  | 'failed'
  | 'idle'
  | 'timeout'
  | 'misfired';

// 执行状态枚举
export type ExecutionStatus = 'success' | 'failed' | 'timeout' | 'running';

// 任务信息
export interface JobInfo {
  id: string;
  name: string;
  trigger: string;
  next_run_time: string | null;
  pending: boolean;
  status: TaskStatus;
  
  // 详细信息（可选）
  func?: string;
  args?: any[];
  kwargs?: Record<string, any>;
  executor?: string;
  max_instances?: number;
  misfire_grace_time?: number;
  coalesce?: boolean;
}

// 任务执行历史
export interface TaskExecutionResponse {
  id: number;
  job_id: string;
  job_name: string;
  status: ExecutionStatus;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  result: Record<string, any> | null;
  error_message: string | null;
  created_at: string;
}

// 任务统计
export interface JobStatsResponse {
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  success_rate: number;
  avg_duration_seconds: number;
}

// 创建任务请求
export interface JobCreateRequest {
  func: string;
  name: string;
  trigger: string;
  trigger_args: Record<string, any>;
  args?: any[];
  kwargs?: Record<string, any>;
  max_retries?: number;
  timeout?: number;
}

// 更新任务调度
export interface JobScheduleUpdate {
  trigger?: string;
  trigger_args?: Record<string, any>;
}

// 系统信息
export interface SystemInfo {
  stats?: {
    total_jobs: number;
    active_jobs: number;
    paused_jobs: number;
    task_types: Record<string, number>;
    scheduler_running: boolean;
  };
  health?: {
    total_jobs: number;
    healthy_jobs: number;
    unhealthy_jobs: Array<{
      job_id: string;
      name: string;
      status: TaskStatus;
      next_run_time: string | null;
    }>;
    scheduler_running: boolean;
    health_score: number;
  };
}

// 任务过滤条件
export interface TaskFilters {
  status?: TaskStatus;
  search?: string;
}
```

## 2. 修改 ScraperLayout 为通用的管理布局

```typescript
// frontend/src/components/Layout/ManagementLayout.tsx
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Toolbar,
  AppBar,
  Container,
  Button,
  Divider,
} from '@mui/material';
import {
  SmartToy as BotIcon,
  PlayArrow as SessionIcon,
  Article as ContentIcon,
  ArrowBack as ArrowBackIcon,
  Schedule as TaskIcon,
  Dashboard as DashboardIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';

interface ManagementLayoutProps {
  children: React.ReactNode;
}

const DRAWER_WIDTH = 240;

const menuSections = [
  {
    title: '爬虫管理',
    items: [
      {
        text: 'Bot配置',
        icon: <BotIcon />,
        path: '/management/scraper/bots',
        implemented: true,
      },
      {
        text: '会话管理',
        icon: <SessionIcon />,
        path: '/management/scraper/sessions',
        implemented: true,
      },
      {
        text: '内容管理',
        icon: <ContentIcon />,
        path: '/management/scraper/content',
        implemented: false,
      },
    ],
  },
  {
    title: '系统管理',
    items: [
      {
        text: '任务调度',
        icon: <TaskIcon />,
        path: '/management/tasks',
        implemented: true,
      },
      {
        text: '系统监控',
        icon: <DashboardIcon />,
        path: '/management/monitoring',
        implemented: false,
      },
      {
        text: '系统设置',
        icon: <SettingsIcon />,
        path: '/management/settings',
        implemented: false,
      },
    ],
  },
];

const ManagementLayout: React.FC<ManagementLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleMenuClick = (path: string, implemented: boolean) => {
    if (implemented) {
      navigate(path);
    }
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          width: `calc(100% - ${DRAWER_WIDTH}px)`,
          ml: `${DRAWER_WIDTH}px`,
        }}
      >
        <Toolbar>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/dashboard')}
            sx={{ mr: 2, color: 'white' }}
          >
            返回仪表板
          </Button>
          <Typography variant="h6" noWrap component="div">
            综合管理系统
          </Typography>
        </Toolbar>
      </AppBar>

      <Drawer
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
          },
        }}
        variant="permanent"
        anchor="left"
      >
        <Toolbar>
          <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
            管理功能
          </Typography>
        </Toolbar>
        
        <List>
          {menuSections.map((section, sectionIndex) => (
            <React.Fragment key={section.title}>
              {sectionIndex > 0 && <Divider sx={{ my: 1 }} />}
              <ListItem>
                <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 1 }}>
                  {section.title}
                </Typography>
              </ListItem>
              {section.items.map((item) => (
                <ListItem key={item.text} disablePadding>
                  <ListItemButton
                    selected={location.pathname === item.path}
                    onClick={() => handleMenuClick(item.path, item.implemented)}
                    disabled={!item.implemented}
                    sx={{
                      '&.Mui-selected': {
                        backgroundColor: 'primary.main',
                        color: 'white',
                        '&:hover': {
                          backgroundColor: 'primary.dark',
                        },
                        '& .MuiListItemIcon-root': {
                          color: 'white',
                        },
                      },
                      '&.Mui-disabled': {
                        opacity: 0.5,
                      },
                    }}
                  >
                    <ListItemIcon
                      sx={{
                        color: location.pathname === item.path ? 'white' : 'inherit',
                      }}
                    >
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={item.text}
                      secondary={!item.implemented ? '(即将推出)' : ''}
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </React.Fragment>
          ))}
        </List>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          bgcolor: 'background.default',
          p: 3,
          width: `calc(100% - ${DRAWER_WIDTH}px)`,
        }}
      >
        <Toolbar />
        <Container maxWidth="xl">
          {children}
        </Container>
      </Box>
    </Box>
  );
};

export default ManagementLayout;
```

## 3. 创建任务管理相关组件

### 任务卡片组件

```typescript
// frontend/src/components/Tasks/TaskCard.tsx
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
  LinearProgress,
} from '@mui/material';
import {
  PlayArrow as RunIcon,
  Pause as PauseIcon,
  Delete as DeleteIcon,
  History as HistoryIcon,
  Schedule as ScheduleIcon,
  Error as ErrorIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import { JobInfo } from '../../types/task';

interface TaskCardProps {
  task: JobInfo;
  onRun: (task: JobInfo) => void;
  onPause: (task: JobInfo) => void;
  onResume: (task: JobInfo) => void;
  onDelete: (task: JobInfo) => void;
  onViewHistory: (task: JobInfo) => void;
  disabled?: boolean;
}

const TaskCard: React.FC<TaskCardProps> = ({
  task,
  onRun,
  onPause,
  onResume,
  onDelete,
  onViewHistory,
  disabled = false,
}) => {
  const getStatusColor = (status: string) => {
    const statusColorMap: Record<string, any> = {
      running: 'primary',
      scheduled: 'info',
      paused: 'warning',
      stopped: 'default',
      failed: 'error',
      idle: 'default',
      timeout: 'error',
      misfired: 'warning',
    };
    return statusColorMap[status] || 'default';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <RunIcon />;
      case 'scheduled': return <ScheduleIcon />;
      case 'failed': return <ErrorIcon />;
      case 'idle':
      case 'paused': return <PauseIcon />;
      default: return null;
    }
  };

  const formatNextRunTime = (time: string | null) => {
    if (!time) return '未安排';
    return new Date(time).toLocaleString('zh-CN');
  };

  const isPaused = task.status === 'paused';
  const isRunning = task.status === 'running';

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Typography variant="h6" component="h2" gutterBottom>
            {task.name}
          </Typography>
          <Chip
            label={task.status}
            color={getStatusColor(task.status)}
            size="small"
            icon={getStatusIcon(task.status)}
          />
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          ID: {task.id}
        </Typography>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          触发器: {task.trigger}
        </Typography>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          下次运行: {formatNextRunTime(task.next_run_time)}
        </Typography>

        {task.func && (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            函数: {task.func}
          </Typography>
        )}

        {isRunning && (
          <LinearProgress sx={{ mt: 2 }} />
        )}
      </CardContent>

      <CardActions sx={{ justifyContent: 'space-between' }}>
        <Box>
          <Tooltip title="查看执行历史">
            <IconButton
              onClick={() => onViewHistory(task)}
              disabled={disabled}
              size="small"
            >
              <HistoryIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Box>
          {!isRunning && (
            <Tooltip title="立即执行">
              <IconButton
                onClick={() => onRun(task)}
                disabled={disabled}
                color="primary"
                size="small"
              >
                <RunIcon />
              </IconButton>
            </Tooltip>
          )}
          
          {isPaused ? (
            <Tooltip title="恢复任务">
              <IconButton
                onClick={() => onResume(task)}
                disabled={disabled}
                color="success"
                size="small"
              >
                <SuccessIcon />
              </IconButton>
            </Tooltip>
          ) : (
            <Tooltip title="暂停任务">
              <IconButton
                onClick={() => onPause(task)}
                disabled={disabled || isRunning}
                color="warning"
                size="small"
              >
                <PauseIcon />
              </IconButton>
            </Tooltip>
          )}
          
          <Tooltip title="删除任务">
            <IconButton
              onClick={() => onDelete(task)}
              disabled={disabled || isRunning}
              color="error"
              size="small"
            >
              <DeleteIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </CardActions>
    </Card>
  );
};

export default TaskCard;
```

### 任务历史对话框

```typescript
// frontend/src/components/Tasks/TaskHistoryDialog.tsx
import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  CircularProgress,
  Alert,
  IconButton,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Close as CloseIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  HourglassEmpty as RunningIcon,
  Timelapse as TimeoutIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { TaskExecutionResponse, JobStatsResponse } from '../../types/task';

interface TaskHistoryDialogProps {
  open: boolean;
  jobId: string | null;
  jobName: string;
  onClose: () => void;
}

const TaskHistoryDialog: React.FC<TaskHistoryDialogProps> = ({
  open,
  jobId,
  jobName,
  onClose,
}) => {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));
  const { fetchData, getApiState } = useApiStore();
  
  const [executions, setExecutions] = useState<TaskExecutionResponse[]>([]);
  const [stats, setStats] = useState<JobStatsResponse | null>(null);

  const historyUrl = jobId ? `/v1/tasks/${jobId}/history` : '';
  const statsUrl = jobId ? `/v1/tasks/${jobId}/stats` : '';
  
  const { loading: historyLoading, error: historyError } = getApiState(historyUrl);
  const { loading: statsLoading } = getApiState(statsUrl);

  useEffect(() => {
    if (open && jobId) {
      loadData();
    }
  }, [open, jobId]);

  const loadData = async () => {
    if (!jobId) return;
    
    try {
      const [historyData, statsData] = await Promise.all([
        fetchData<TaskExecutionResponse[]>(historyUrl),
        fetchData<JobStatsResponse>(statsUrl),
      ]);
      
      setExecutions(historyData || []);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load task history:', error);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success': return <SuccessIcon color="success" />;
      case 'failed': return <ErrorIcon color="error" />;
      case 'timeout': return <TimeoutIcon color="warning" />;
      case 'running': return <RunningIcon color="primary" />;
      default: return null;
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      fullScreen={fullScreen}
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h6">
          任务执行历史 - {jobName}
        </Typography>
        <IconButton onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        {/* Statistics Summary */}
        {stats && !statsLoading && (
          <Paper sx={{ p: 2, mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom>
              执行统计
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 2 }}>
              <Box>
                <Typography variant="caption" color="text.secondary">总执行次数</Typography>
                <Typography variant="h6">{stats.total_runs}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">成功次数</Typography>
                <Typography variant="h6" color="success.main">{stats.successful_runs}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">失败次数</Typography>
                <Typography variant="h6" color="error.main">{stats.failed_runs}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">成功率</Typography>
                <Typography variant="h6">{stats.success_rate.toFixed(1)}%</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">平均耗时</Typography>
                <Typography variant="h6">{formatDuration(stats.avg_duration_seconds)}</Typography>
              </Box>
            </Box>
          </Paper>
        )}

        {/* Execution History Table */}
        {historyLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : historyError ? (
          <Alert severity="error">
            加载执行历史失败
          </Alert>
        ) : executions.length === 0 ? (
          <Alert severity="info">
            暂无执行历史
          </Alert>
        ) : (
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>状态</TableCell>
                  <TableCell>开始时间</TableCell>
                  <TableCell>结束时间</TableCell>
                  <TableCell>耗时</TableCell>
                  <TableCell>错误信息</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {executions.map((execution) => (
                  <TableRow key={execution.id}>
                    <TableCell>
                      <Chip
                        icon={getStatusIcon(execution.status)}
                        label={execution.status}
                        size="small"
                        color={execution.status === 'success' ? 'success' : execution.status === 'failed' ? 'error' : 'default'}
                      />
                    </TableCell>
                    <TableCell>{formatDateTime(execution.started_at)}</TableCell>
                    <TableCell>{execution.completed_at ? formatDateTime(execution.completed_at) : '-'}</TableCell>
                    <TableCell>{formatDuration(execution.duration_seconds)}</TableCell>
                    <TableCell>
                      {execution.error_message && (
                        <Typography variant="caption" color="error">
                          {execution.error_message}
                        </Typography>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
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

export default TaskHistoryDialog;
```

### 系统监控面板

```typescript
// frontend/src/components/Tasks/SystemHealthPanel.tsx
import React, { useEffect, useState } from 'react';
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
import { useApiStore } from '../../stores/api-store';
import { SystemInfo } from '../../types/task';

const SystemHealthPanel: React.FC = () => {
  const { fetchData, getApiState } = useApiStore();
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);

  const systemUrl = '/v1/tasks/system?include_health=true&include_stats=true';
  const { loading, error } = getApiState(systemUrl);

  useEffect(() => {
    loadSystemInfo();
    const interval = setInterval(loadSystemInfo, 30000); // 每30秒刷新
    return () => clearInterval(interval);
  }, []);

  const loadSystemInfo = async () => {
    try {
      const data = await fetchData<SystemInfo>(systemUrl);
      setSystemInfo(data);
    } catch (error) {
      console.error('Failed to load system info:', error);
    }
  };

  if (loading && !systemInfo) {
    return (
      <Card sx={{ mb: 3 }}>
        <CardContent sx={{ display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </CardContent>
      </Card>
    );
  }

  if (error || !systemInfo) {
    return null;
  }

  const healthScore = systemInfo.health?.health_score || 0;
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
          {systemInfo.stats && (
            <>
              <Box>
                <Typography variant="caption" color="text.secondary">调度器状态</Typography>
                <Typography variant="body1">
                  <Chip
                    label={systemInfo.stats.scheduler_running ? '运行中' : '已停止'}
                    color={systemInfo.stats.scheduler_running ? 'success' : 'error'}
                    size="small"
                  />
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">总任务数</Typography>
                <Typography variant="h6">{systemInfo.stats.total_jobs}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">活跃任务</Typography>
                <Typography variant="h6">{systemInfo.stats.active_jobs}</Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">暂停任务</Typography>
                <Typography variant="h6">{systemInfo.stats.paused_jobs}</Typography>
              </Box>
            </>
          )}
        </Box>

        {systemInfo.health?.unhealthy_jobs && systemInfo.health.unhealthy_jobs.length > 0 && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              异常任务 ({systemInfo.health.unhealthy_jobs.length})
            </Typography>
            {systemInfo.health.unhealthy_jobs.slice(0, 3).map((job) => (
              <Typography key={job.job_id} variant="caption" display="block">
                • {job.name} - {job.status}
              </Typography>
            ))}
            {systemInfo.health.unhealthy_jobs.length > 3 && (
              <Typography variant="caption" display="block">
                ...还有 {systemInfo.health.unhealthy_jobs.length - 3} 个异常任务
              </Typography>
            )}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};

export default SystemHealthPanel;
```

## 4. 创建任务管理页面

```typescript
// frontend/src/pages/TaskManagementPage.tsx
import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Grid,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Snackbar,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useApiStore } from '../stores/api-store';
import { useAuthStore } from '../stores/auth-store';
import ManagementLayout from '../components/Layout/ManagementLayout';
import TaskCard from '../components/Tasks/TaskCard';
import TaskHistoryDialog from '../components/Tasks/TaskHistoryDialog';
import SystemHealthPanel from '../components/Tasks/SystemHealthPanel';
import { JobInfo, TaskFilters } from '../types/task';

const TaskManagementPage: React.FC = () => {
  const { fetchData, postData, deleteData, getApiState } = useApiStore();
  const { user } = useAuthStore();
  const [tasks, setTasks] = useState<JobInfo[]>([]);
  const [selectedTask, setSelectedTask] = useState<JobInfo | null>(null);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [taskToDelete, setTaskToDelete] = useState<JobInfo | null>(null);
  const [filters, setFilters] = useState<TaskFilters>({});
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  const tasksApiUrl = '/v1/tasks';
  const { loading: tasksLoading, error: tasksError } = getApiState(tasksApiUrl);

  // Check if user is superuser
  const isSuperuser = user?.is_superuser || false;

  const loadTasks = useCallback(async () => {
    if (!isSuperuser) return;
    
    try {
      const data = await fetchData<JobInfo[]>(tasksApiUrl);
      setTasks(data || []);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    }
  }, [fetchData, tasksApiUrl, isSuperuser]);

  useEffect(() => {
    if (isSuperuser) {
      loadTasks();
      const interval = setInterval(loadTasks, 10000); // 每10秒刷新
      return () => clearInterval(interval);
    }
  }, [loadTasks, isSuperuser]);

  const handleTaskAction = async (taskId: string, action: string) => {
    try {
      await postData(`/v1/tasks/${taskId}/action?action=${action}`, {});
      setSnackbarMessage(`任务操作成功: ${action}`);
      setSnackbarOpen(true);
      await loadTasks();
    } catch (error) {
      console.error(`Failed to ${action} task:`, error);
      setSnackbarMessage(`任务操作失败: ${action}`);
      setSnackbarOpen(true);
    }
  };

  const handleRunTask = (task: JobInfo) => {
    handleTaskAction(task.id, 'run');
  };

  const handlePauseTask = (task: JobInfo) => {
    handleTaskAction(task.id, 'pause');
  };

  const handleResumeTask = (task: JobInfo) => {
    handleTaskAction(task.id, 'resume');
  };

  const handleDeleteTask = (task: JobInfo) => {
    setTaskToDelete(task);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!taskToDelete) return;

    try {
      await deleteData(`/v1/tasks/${taskToDelete.id}`);
      setSnackbarMessage('任务删除成功');
      setSnackbarOpen(true);
      await loadTasks();
      setDeleteDialogOpen(false);
      setTaskToDelete(null);
    } catch (error) {
      console.error('Failed to delete task:', error);
      setSnackbarMessage('任务删除失败');
      setSnackbarOpen(true);
    }
  };

  const handleViewHistory = (task: JobInfo) => {
    setSelectedTask(task);
    setHistoryDialogOpen(true);
  };

  const filteredTasks = tasks.filter(task => {
    if (filters.status && task.status !== filters.status) {
      return false;
    }
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      return task.name.toLowerCase().includes(searchLower) || 
             task.id.toLowerCase().includes(searchLower);
    }
    return true;
  });

  if (!isSuperuser) {
    return (
      <ManagementLayout>
        <Alert severity="error" sx={{ mt: 4 }}>
          您没有权限访问任务管理功能。需要超级管理员权限。
        </Alert>
      </ManagementLayout>
    );
  }

  return (
    <ManagementLayout>
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" gutterBottom>
            任务调度管理
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={loadTasks}
              disabled={tasksLoading}
            >
              刷新
            </Button>
          </Box>
        </Box>

        {/* System Health Panel */}
        <SystemHealthPanel />

        {/* Filter Bar */}
        <Box sx={{ mb: 3, display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            label="搜索任务"
            variant="outlined"
            size="small"
            value={filters.search || ''}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            sx={{ minWidth: 200 }}
          />
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>状态筛选</InputLabel>
            <Select
              value={filters.status || ''}
              label="状态筛选"
              onChange={(e) => setFilters({ ...filters, status: e.target.value as any })}
            >
              <MenuItem value="">全部</MenuItem>
              <MenuItem value="running">运行中</MenuItem>
              <MenuItem value="scheduled">已调度</MenuItem>
              <MenuItem value="paused">已暂停</MenuItem>
              <MenuItem value="failed">失败</MenuItem>
            </Select>
          </FormControl>
        </Box>

        {tasksError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {tasksError.message || '加载失败，请稍后重试'}
          </Alert>
        )}

        {tasksLoading && tasks.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress />
          </Box>
        ) : filteredTasks.length === 0 ? (
          <Box sx={{ textAlign: 'center', mt: 4 }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              没有找到任务
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {filters.search || filters.status ? '尝试调整筛选条件' : '系统中还没有配置任何定时任务'}
            </Typography>
          </Box>
        ) : (
          <Grid container spacing={3}>
            {filteredTasks.map((task) => (
              <Grid item xs={12} sm={6} lg={4} key={task.id}>
                <TaskCard
                  task={task}
                  onRun={handleRunTask}
                  onPause={handlePauseTask}
                  onResume={handleResumeTask}
                  onDelete={handleDeleteTask}
                  onViewHistory={handleViewHistory}
                  disabled={tasksLoading}
                />
              </Grid>
            ))}
          </Grid>
        )}

        {/* Task History Dialog */}
        <TaskHistoryDialog
          open={historyDialogOpen}
          jobId={selectedTask?.id || null}
          jobName={selectedTask?.name || ''}
          onClose={() => setHistoryDialogOpen(false)}
        />

        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
          <DialogTitle>确认删除</DialogTitle>
          <DialogContent>
            <Typography>
              确定要删除任务 "{taskToDelete?.name}" 吗？此操作无法撤销。
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteDialogOpen(false)}>取消</Button>
            <Button onClick={confirmDelete} color="error" variant="contained">
              删除
            </Button>
          </DialogActions>
        </Dialog>

        {/* Snackbar for feedback */}
        <Snackbar
          open={snackbarOpen}
          autoHideDuration={6000}
          onClose={() => setSnackbarOpen(false)}
          message={snackbarMessage}
        />
      </Box>
    </ManagementLayout>
  );
};

export default TaskManagementPage;
```

## 5. 更新路由配置

```typescript
// frontend/src/routes.tsx
import React from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { TokenExpiryDialog } from './components/TokenExpiryDialog';
import { useUIStore } from './stores/index';
import DemoPage from './pages/DemoPage';
import UserPage from './pages/UserPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ProfilePage from './pages/ProfilePage';
import ForgotPasswordPage from './pages/ForgotPasswordPage';
import ResetPasswordPage from './pages/ResetPasswordPage';
import BotManagementPage from './pages/BotManagementPage';
import SessionManagementPage from './pages/SessionManagementPage';
import TaskManagementPage from './pages/TaskManagementPage';

const AppRoutes: React.FC = () => {
  const navigate = useNavigate();
  const { tokenExpiryDialogOpen, hideTokenExpiryDialog } = useUIStore();

  const handleTokenExpiryConfirm = () => {
    hideTokenExpiryDialog();
    navigate('/login');
  };

  return (
    <>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        
        {/* 公共路由 */}
        <Route path="/login" element={
          <ProtectedRoute requireAuth={false}>
            <LoginPage />
          </ProtectedRoute>
        } />
        <Route path="/register" element={
          <ProtectedRoute requireAuth={false}>
            <RegisterPage />
          </ProtectedRoute>
        } />
        
        {/* 密码重置相关路由 */}
        <Route path="/forgot-password" element={
          <ProtectedRoute requireAuth={false}>
            <ForgotPasswordPage />
          </ProtectedRoute>
        } />
        <Route path="/reset-password" element={
          <ProtectedRoute requireAuth={false}>
            <ResetPasswordPage />
          </ProtectedRoute>
        } />
        
        {/* 受保护的路由 */}
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        } />
        <Route path="/profile" element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        } />
        <Route path="/user" element={
          <ProtectedRoute>
            <UserPage />
          </ProtectedRoute>
        } />
        <Route path="/demo" element={
          <ProtectedRoute>
            <DemoPage />
          </ProtectedRoute>
        } />
        
        {/* 综合管理路由 */}
        <Route path="/management" element={<Navigate to="/management/scraper/bots" replace />} />
        <Route path="/management/scraper/bots" element={
          <ProtectedRoute>
            <BotManagementPage />
          </ProtectedRoute>
        } />
        <Route path="/management/scraper/sessions" element={
          <ProtectedRoute>
            <SessionManagementPage />
          </ProtectedRoute>
        } />
        <Route path="/management/tasks" element={
          <ProtectedRoute>
            <TaskManagementPage />
          </ProtectedRoute>
        } />
        
        {/* 保持向后兼容性 */}
        <Route path="/scraper" element={<Navigate to="/management/scraper/bots" replace />} />
        <Route path="/scraper/*" element={<Navigate to="/management/scraper/bots" replace />} />
        
        {/* 错误页面 */}
        {/* <Route path="/unauthorized" element={<UnauthorizedPage />} />
        <Route path="*" element={<NotFoundPage />} /> */}
      </Routes>

      {/* Token过期确认对话框 */}
      <TokenExpiryDialog
        open={tokenExpiryDialogOpen}
        onConfirm={handleTokenExpiryConfirm}
      />
    </>
  );
};

export default AppRoutes;
```

## 6. 更新 DashboardPage 的按钮

```typescript
// frontend/src/pages/DashboardPage.tsx
// 找到原来的爬虫管理按钮，修改为：

<Button
  variant="outlined"
  onClick={() => navigate('/management')}
  fullWidth
>
  综合管理系统
</Button>
```

## 7. 更新所有爬虫相关页面的布局引用

由于我们创建了新的 `ManagementLayout`，需要更新所有爬虫相关页面：

```typescript
// frontend/src/pages/BotManagementPage.tsx
// 将 import ScraperLayout 改为：
import ManagementLayout from '../components/Layout/ManagementLayout';

// 将 <ScraperLayout> 改为 <ManagementLayout>

// frontend/src/pages/SessionManagementPage.tsx
// 同样的修改
```

## 8. 创建组件索引文件

```typescript
// frontend/src/components/Tasks/index.ts
export { default as TaskCard } from './TaskCard';
export { default as TaskHistoryDialog } from './TaskHistoryDialog';
export { default as SystemHealthPanel } from './SystemHealthPanel';
```

现在你已经有了一个完整的任务管理系统，集成在综合管理系统中。这个系统包括：

1. **任务监控**：显示所有任务状态、下次运行时间等
2. **任务操作**：暂停、恢复、立即执行、删除任务
3. **执行历史**：查看每个任务的执行历史和统计信息
4. **系统健康**：监控整个任务调度系统的健康状态
5. **权限控制**：只有超级管理员可以访问任务管理功能

综合管理系统现在包含了爬虫管理和任务调度两大模块，未来可以很容易地添加更多功能模块。
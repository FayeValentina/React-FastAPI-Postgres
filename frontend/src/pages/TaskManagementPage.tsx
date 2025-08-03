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
import { Refresh as RefreshIcon } from '@mui/icons-material';
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
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

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

  const handleRefresh = useCallback(async () => {
    await loadTasks();
    setRefreshTrigger(prev => prev + 1); // 触发 SystemHealthPanel 刷新
  }, [loadTasks]);

  useEffect(() => {
    if (isSuperuser) {
      loadTasks();
      const interval = setInterval(loadTasks, 60000); // 每60秒刷新
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
              onClick={handleRefresh}
              disabled={tasksLoading}
            >
              刷新
            </Button>
          </Box>
        </Box>

        {/* System Health Panel */}
        <SystemHealthPanel refreshTrigger={refreshTrigger} />

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
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
  Checkbox,
  FormControlLabel,
  Chip,
} from '@mui/material';
import { 
  Refresh as RefreshIcon,
  CleaningServices as CleanupIcon,
  PlayArrow as BatchPlayIcon,
  Pause as BatchPauseIcon,
  Delete as BatchDeleteIcon,
} from '@mui/icons-material';
import { useApiStore } from '../stores/api-store';
import { useAuthStore } from '../stores/auth-store';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import { useKeyboardShortcuts, SHORTCUTS } from '../hooks/useKeyboardShortcuts';
import AutoRefreshControl from '../components/Common/AutoRefreshControl';
import LoadingState from '../components/Common/LoadingState';
import ErrorBoundary from '../components/Common/ErrorBoundary';
import ManagementLayout from '../components/Layout/ManagementLayout';
import TaskCard from '../components/Tasks/TaskCard';
import TaskDetailDialog from '../components/Tasks/TaskDetailDialog';
import CleanupManagerDialog from '../components/Tasks/CleanupManagerDialog';
import BatchUpdateDialog from '../components/Tasks/BatchUpdateDialog';
import SystemHealthPanel from '../components/Tasks/SystemHealthPanel';
import { EnhancedSchedule, TaskFilters, CleanupConfig, BatchUpdateConfig } from '../types/task';

const TaskManagementPage: React.FC = () => {
  const { fetchData, postData, deleteData, getApiState } = useApiStore();
  const { user } = useAuthStore();
  const [schedules, setSchedules] = useState<EnhancedSchedule[]>([]);
  const [selectedSchedule, setSelectedSchedule] = useState<EnhancedSchedule | null>(null);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [scheduleToDelete, setScheduleToDelete] = useState<EnhancedSchedule | null>(null);
  const [cleanupDialogOpen, setCleanupDialogOpen] = useState(false);
  const [batchUpdateDialogOpen, setBatchUpdateDialogOpen] = useState(false);
  const [filters, setFilters] = useState<TaskFilters>({});
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);
  
  // 批量操作相关状态
  const [selectedScheduleIds, setSelectedScheduleIds] = useState<string[]>([]);
  const [batchMode, setBatchMode] = useState(false);
  const [autoRefreshInterval, setAutoRefreshInterval] = useState(60000); // 60秒

  const schedulesApiUrl = '/v1/tasks/schedules?enhanced=true';
  const { loading: schedulesLoading, error: schedulesError } = getApiState(schedulesApiUrl);

  // Check if user is superuser
  const isSuperuser = user?.is_superuser || false;

  const loadSchedules = useCallback(async () => {
    if (!isSuperuser) return;
    
    try {
      const data = await fetchData<EnhancedSchedule[]>(schedulesApiUrl);
      setSchedules(data || []);
    } catch (error) {
      console.error('Failed to load schedules:', error);
    }
  }, [fetchData, schedulesApiUrl, isSuperuser]);

  const handleRefresh = useCallback(async () => {
    await loadSchedules();
    setRefreshTrigger(prev => prev + 1); // 触发 SystemHealthPanel 刷新
  }, [loadSchedules]);

  // 使用自动刷新Hook
  const autoRefresh = useAutoRefresh(
    handleRefresh,
    {
      interval: autoRefreshInterval,
      enabled: true,
      immediate: isSuperuser,
    }
  );

  // 处理刷新间隔变化
  const handleIntervalChange = useCallback((newInterval: number) => {
    setAutoRefreshInterval(newInterval);
    autoRefresh.setInterval(newInterval);
  }, [autoRefresh]);

  // 键盘快捷键
  useKeyboardShortcuts([
    {
      ...SHORTCUTS.REFRESH,
      callback: autoRefresh.refresh,
      description: '刷新任务列表',
      disabled: schedulesLoading,
    },
    {
      ...SHORTCUTS.CTRL_R,
      callback: autoRefresh.refresh,
      description: '刷新任务列表',
      disabled: schedulesLoading,
    },
    {
      ...SHORTCUTS.SPACE,
      callback: autoRefresh.toggle,
      description: '切换自动刷新',
      disabled: schedulesLoading,
    },
    {
      ...SHORTCUTS.ESCAPE,
      callback: () => {
        if (historyDialogOpen) {
          setHistoryDialogOpen(false);
        } else if (deleteDialogOpen) {
          setDeleteDialogOpen(false);
        } else if (cleanupDialogOpen) {
          setCleanupDialogOpen(false);
        } else if (batchUpdateDialogOpen) {
          setBatchUpdateDialogOpen(false);
        } else if (batchMode) {
          setBatchMode(false);
          setSelectedScheduleIds([]);
        }
      },
      description: '关闭对话框或退出批量模式',
    },
    {
      key: 'b',
      ctrlKey: true,
      callback: () => {
        setBatchMode(!batchMode);
        setSelectedScheduleIds([]);
      },
      description: '切换批量操作模式',
      disabled: schedulesLoading,
    },
  ]);

  // 批量操作处理函数
  const handleBatchAction = async (action: 'pause' | 'resume' | 'delete') => {
    if (selectedScheduleIds.length === 0) {
      setSnackbarMessage('请选择要操作的任务');
      setSnackbarOpen(true);
      return;
    }

    try {
      const updates: BatchUpdateConfig = {
        schedule_ids: selectedScheduleIds,
        updates: { action }
      };
      
      await postData('/v1/tasks/schedules/batch-update', updates);
      setSnackbarMessage(`批量${action === 'pause' ? '暂停' : action === 'resume' ? '恢复' : '删除'}操作成功`);
      setSnackbarOpen(true);
      setSelectedScheduleIds([]);
      setBatchMode(false);
      await loadSchedules();
    } catch (error) {
      console.error(`Failed to batch ${action}:`, error);
      setSnackbarMessage(`批量操作失败: ${action}`);
      setSnackbarOpen(true);
    }
  };

  // 清理任务处理函数
  const handleCleanup = async () => {
    try {
      const cleanupConfig: CleanupConfig = { action: 'trigger' };
      await postData('/v1/tasks/cleanup', cleanupConfig);
      setSnackbarMessage('清理操作已启动');
      setSnackbarOpen(true);
      setCleanupDialogOpen(false);
      await loadSchedules();
    } catch (error) {
      console.error('Failed to trigger cleanup:', error);
      setSnackbarMessage('清理操作失败');
      setSnackbarOpen(true);
    }
  };

  const handleScheduleAction = async (scheduleId: string, action: string) => {
    try {
      await postData(`/v1/tasks/schedules/${scheduleId}/action?action=${action}`, {});
      setSnackbarMessage(`任务操作成功: ${action}`);
      setSnackbarOpen(true);
      await loadSchedules();
    } catch (error) {
      console.error(`Failed to ${action} schedule:`, error);
      setSnackbarMessage(`任务操作失败: ${action}`);
      setSnackbarOpen(true);
    }
  };

  const handleRunSchedule = (schedule: EnhancedSchedule) => {
    handleScheduleAction(schedule.schedule_id, 'run');
  };

  const handlePauseSchedule = (schedule: EnhancedSchedule) => {
    handleScheduleAction(schedule.schedule_id, 'pause');
  };

  const handleResumeSchedule = (schedule: EnhancedSchedule) => {
    handleScheduleAction(schedule.schedule_id, 'resume');
  };

  const handleDeleteSchedule = (schedule: EnhancedSchedule) => {
    setScheduleToDelete(schedule);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!scheduleToDelete) return;

    try {
      await deleteData(`/v1/tasks/schedules/${scheduleToDelete.schedule_id}`);
      setSnackbarMessage('任务删除成功');
      setSnackbarOpen(true);
      await loadSchedules();
      setDeleteDialogOpen(false);
      setScheduleToDelete(null);
    } catch (error) {
      console.error('Failed to delete schedule:', error);
      setSnackbarMessage('任务删除失败');
      setSnackbarOpen(true);
    }
  };

  const handleViewHistory = (schedule: EnhancedSchedule) => {
    setSelectedSchedule(schedule);
    setHistoryDialogOpen(true);
  };

  // 批量选择处理函数
  const handleSelectSchedule = (scheduleId: string, selected: boolean) => {
    if (selected) {
      setSelectedScheduleIds(prev => [...prev, scheduleId]);
    } else {
      setSelectedScheduleIds(prev => prev.filter(id => id !== scheduleId));
    }
  };

  const handleSelectAll = () => {
    const allIds = filteredSchedules.map(s => s.schedule_id);
    setSelectedScheduleIds(allIds);
  };

  const handleDeselectAll = () => {
    setSelectedScheduleIds([]);
  };

  const filteredSchedules = schedules.filter(schedule => {
    if (filters.status && schedule.computed_status !== filters.status) {
      return false;
    }
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      return schedule.name.toLowerCase().includes(searchLower) || 
             schedule.schedule_id.toLowerCase().includes(searchLower);
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
    <ErrorBoundary>
      <ManagementLayout>
        <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" gutterBottom>
            任务调度管理
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              startIcon={<CleanupIcon />}
              onClick={() => setCleanupDialogOpen(true)}
              disabled={schedulesLoading}
            >
              清理管理
            </Button>
            <Button
              variant={batchMode ? 'contained' : 'outlined'}
              onClick={() => {
                setBatchMode(!batchMode);
                setSelectedScheduleIds([]);
              }}
              disabled={schedulesLoading}
            >
              批量操作
            </Button>
            {batchMode && selectedScheduleIds.length > 0 && (
              <Button
                variant="contained"
                color="secondary"
                onClick={() => setBatchUpdateDialogOpen(true)}
                disabled={schedulesLoading}
              >
                高级批量更新
              </Button>
            )}
            <AutoRefreshControl
              isRunning={autoRefresh.isRunning}
              interval={autoRefreshInterval}
              onStart={autoRefresh.start}
              onStop={autoRefresh.stop}
              onToggle={autoRefresh.toggle}
              onRefresh={autoRefresh.refresh}
              onSetInterval={handleIntervalChange}
              disabled={schedulesLoading}
            />
          </Box>
        </Box>

        {/* Batch Operations Bar */}
        {batchMode && (
          <Box sx={{ mb: 3, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="body2" color="text.secondary">
                已选择 {selectedScheduleIds.length} 个任务
              </Typography>
              {selectedScheduleIds.length > 0 && (
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    size="small"
                    startIcon={<BatchPauseIcon />}
                    onClick={() => handleBatchAction('pause')}
                  >
                    批量暂停
                  </Button>
                  <Button
                    size="small"
                    startIcon={<BatchPlayIcon />}
                    onClick={() => handleBatchAction('resume')}
                  >
                    批量恢复
                  </Button>
                  <Button
                    size="small"
                    startIcon={<BatchDeleteIcon />}
                    onClick={() => handleBatchAction('delete')}
                    color="error"
                  >
                    批量删除
                  </Button>
                </Box>
              )}
              <Box sx={{ ml: 'auto', display: 'flex', gap: 1 }}>
                <Button size="small" onClick={handleSelectAll}>全选</Button>
                <Button size="small" onClick={handleDeselectAll}>取消全选</Button>
              </Box>
            </Box>
          </Box>
        )}

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

        {schedulesError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {schedulesError.message || '加载失败，请稍后重试'}
          </Alert>
        )}

        {schedulesLoading && schedules.length === 0 ? (
          <LoadingState
            type="card"
            count={6}
            message="正在加载任务调度信息..."
          />
        ) : filteredSchedules.length === 0 ? (
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
            {filteredSchedules.map((schedule) => (
              <Grid item xs={12} sm={6} lg={4} key={schedule.schedule_id}>
                <Box sx={{ position: 'relative' }}>
                  {batchMode && (
                    <Checkbox
                      checked={selectedScheduleIds.includes(schedule.schedule_id)}
                      onChange={(e) => handleSelectSchedule(schedule.schedule_id, e.target.checked)}
                      sx={{ position: 'absolute', top: 8, left: 8, zIndex: 1 }}
                    />
                  )}
                  <TaskCard
                    task={{
                      id: schedule.schedule_id,
                      name: schedule.name,
                      trigger: schedule.trigger,
                      next_run_time: schedule.next_run_time,
                      pending: schedule.pending,
                      status: schedule.computed_status || 'idle',
                    }}
                    schedule={schedule}
                    onRun={handleRunSchedule}
                    onPause={handlePauseSchedule}
                    onResume={handleResumeSchedule}
                    onDelete={handleDeleteSchedule}
                    onViewHistory={handleViewHistory}
                    disabled={schedulesLoading}
                    batchMode={batchMode}
                  />
                </Box>
              </Grid>
            ))}
          </Grid>
        )}

        {/* Task Detail Dialog */}
        <TaskDetailDialog
          open={historyDialogOpen}
          jobId={selectedSchedule?.schedule_id || null}
          jobName={selectedSchedule?.name || ''}
          schedule={selectedSchedule || undefined}
          onClose={() => setHistoryDialogOpen(false)}
        />

        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
          <DialogTitle>确认删除</DialogTitle>
          <DialogContent>
            <Typography>
              确定要删除任务 "{scheduleToDelete?.name}" 吗？此操作无法撤销。
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteDialogOpen(false)}>取消</Button>
            <Button onClick={confirmDelete} color="error" variant="contained">
              删除
            </Button>
          </DialogActions>
        </Dialog>

        {/* Cleanup Management Dialog */}
        <CleanupManagerDialog
          open={cleanupDialogOpen}
          onClose={() => setCleanupDialogOpen(false)}
          onCleanupComplete={() => {
            setSnackbarMessage('清理操作已完成');
            setSnackbarOpen(true);
            loadSchedules();
          }}
        />

        {/* Batch Update Dialog */}
        <BatchUpdateDialog
          open={batchUpdateDialogOpen}
          onClose={() => {
            setBatchUpdateDialogOpen(false);
            setSelectedScheduleIds([]);
            setBatchMode(false);
          }}
          schedules={schedules}
          selectedScheduleIds={selectedScheduleIds}
          onUpdateComplete={() => {
            setSnackbarMessage('批量更新操作已完成');
            setSnackbarOpen(true);
            loadSchedules();
          }}
        />

        {/* Snackbar for feedback */}
        <Snackbar
          open={snackbarOpen}
          autoHideDuration={6000}
          onClose={() => setSnackbarOpen(false)}
          message={snackbarMessage}
        />
        </Box>
      </ManagementLayout>
    </ErrorBoundary>
  );
};

export default TaskManagementPage;
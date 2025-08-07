import React, { useEffect, useState, useCallback } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  Box,
  Chip,
  IconButton,
  Tooltip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  PlayCircle as ActiveIcon,
  Cancel as CancelIcon,
  Refresh as RefreshIcon,
  Info as InfoIcon,
  Worker as WorkerIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { ActiveTask } from '../../types/task';

interface ActiveTasksPanelProps {
  refreshTrigger?: number;
}

const ActiveTasksPanel: React.FC<ActiveTasksPanelProps> = ({ refreshTrigger = 0 }) => {
  const { fetchData, postData, getApiState } = useApiStore();
  
  const [activeTasks, setActiveTasks] = useState<ActiveTask[]>([]);
  const [selectedTask, setSelectedTask] = useState<ActiveTask | null>(null);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [taskToCancel, setTaskToCancel] = useState<ActiveTask | null>(null);

  const activeTasksUrl = '/v1/tasks/active-tasks';
  const { loading, error } = getApiState(activeTasksUrl);

  const loadActiveTasks = useCallback(async () => {
    try {
      const data = await fetchData<ActiveTask[]>(activeTasksUrl);
      setActiveTasks(data || []);
    } catch (error) {
      console.error('Failed to load active tasks:', error);
    }
  }, [fetchData, activeTasksUrl]);

  useEffect(() => {
    loadActiveTasks();
  }, [loadActiveTasks, refreshTrigger]);

  const handleCancelTask = async (task: ActiveTask) => {
    setTaskToCancel(task);
    setCancelDialogOpen(true);
  };

  const confirmCancelTask = async () => {
    if (!taskToCancel) return;

    try {
      await postData(`/v1/tasks/tasks/${taskToCancel.task_id}/cancel`, {});
      setCancelDialogOpen(false);
      setTaskToCancel(null);
      await loadActiveTasks();
    } catch (error) {
      console.error('Failed to cancel task:', error);
    }
  };

  const handleViewTaskDetails = (task: ActiveTask) => {
    setSelectedTask(task);
  };

  const formatDuration = (startTime: string) => {
    const start = new Date(startTime);
    const now = new Date();
    const diffMs = now.getTime() - start.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffSeconds = Math.floor((diffMs % (1000 * 60)) / 1000);
    
    if (diffMinutes > 0) {
      return `${diffMinutes}分${diffSeconds}秒`;
    }
    return `${diffSeconds}秒`;
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  const getTaskTypeColor = (taskName: string) => {
    if (taskName.includes('scrape') || taskName.includes('reddit')) {
      return 'primary';
    } else if (taskName.includes('cleanup')) {
      return 'warning';
    } else if (taskName.includes('email')) {
      return 'info';
    }
    return 'default';
  };

  const renderTaskDetailsDialog = () => (
    <Dialog
      open={!!selectedTask}
      onClose={() => setSelectedTask(null)}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle>
        任务详情 - {selectedTask?.name}
      </DialogTitle>
      <DialogContent>
        {selectedTask && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>基本信息</Typography>
            <Table size="small">
              <TableBody>
                <TableRow>
                  <TableCell component="th" scope="row">任务ID</TableCell>
                  <TableCell>{selectedTask.task_id}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell component="th" scope="row">任务名称</TableCell>
                  <TableCell>{selectedTask.name}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell component="th" scope="row">工作节点</TableCell>
                  <TableCell>
                    <Chip 
                      icon={<WorkerIcon />}
                      label={selectedTask.worker} 
                      size="small" 
                      color="primary" 
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell component="th" scope="row">开始时间</TableCell>
                  <TableCell>{formatDateTime(selectedTask.time_start)}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell component="th" scope="row">运行时长</TableCell>
                  <TableCell>{formatDuration(selectedTask.time_start)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>

            {selectedTask.args && selectedTask.args.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>参数</Typography>
                <Box component="pre" sx={{ 
                  bgcolor: 'grey.100', 
                  p: 1, 
                  borderRadius: 1, 
                  fontSize: '0.75rem',
                  overflow: 'auto',
                  maxHeight: '200px'
                }}>
                  {JSON.stringify(selectedTask.args, null, 2)}
                </Box>
              </Box>
            )}

            {selectedTask.kwargs && Object.keys(selectedTask.kwargs).length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" gutterBottom>关键字参数</Typography>
                <Box component="pre" sx={{ 
                  bgcolor: 'grey.100', 
                  p: 1, 
                  borderRadius: 1, 
                  fontSize: '0.75rem',
                  overflow: 'auto',
                  maxHeight: '200px'
                }}>
                  {JSON.stringify(selectedTask.kwargs, null, 2)}
                </Box>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setSelectedTask(null)}>关闭</Button>
      </DialogActions>
    </Dialog>
  );

  const renderCancelConfirmDialog = () => (
    <Dialog open={cancelDialogOpen} onClose={() => setCancelDialogOpen(false)}>
      <DialogTitle>确认取消任务</DialogTitle>
      <DialogContent>
        <Typography>
          确定要取消任务 "{taskToCancel?.name}" 吗？
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
          任务ID: {taskToCancel?.task_id}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          工作节点: {taskToCancel?.worker}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setCancelDialogOpen(false)}>取消</Button>
        <Button onClick={confirmCancelTask} color="error" variant="contained">
          确认取消
        </Button>
      </DialogActions>
    </Dialog>
  );

  return (
    <>
      <Card>
        <CardHeader
          avatar={<ActiveIcon color="primary" />}
          title="活跃任务"
          subheader={`当前运行中的任务 (${activeTasks.length})`}
          action={
            <IconButton onClick={loadActiveTasks} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          }
        />
        <CardContent>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          ) : error ? (
            <Alert severity="error">
              加载活跃任务失败
            </Alert>
          ) : activeTasks.length === 0 ? (
            <Alert severity="info">
              当前没有运行中的任务
            </Alert>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>任务名称</TableCell>
                    <TableCell>工作节点</TableCell>
                    <TableCell>开始时间</TableCell>
                    <TableCell>运行时长</TableCell>
                    <TableCell align="right">操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {activeTasks.map((task, index) => (
                    <TableRow key={task.task_id || index}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Chip
                            label={task.name.split('.').pop() || task.name}
                            size="small"
                            color={getTaskTypeColor(task.name) as 'primary' | 'warning' | 'info' | 'default'}
                            variant="outlined"
                          />
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          icon={<WorkerIcon />}
                          label={task.worker} 
                          size="small" 
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">
                          {formatDateTime(task.time_start)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip 
                          label={formatDuration(task.time_start)}
                          size="small"
                          color="success"
                          variant="filled"
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <Tooltip title="查看详情">
                            <IconButton 
                              size="small"
                              onClick={() => handleViewTaskDetails(task)}
                            >
                              <InfoIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="取消任务">
                            <IconButton 
                              size="small" 
                              color="error"
                              onClick={() => handleCancelTask(task)}
                            >
                              <CancelIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {renderTaskDetailsDialog()}
      {renderCancelConfirmDialog()}
    </>
  );
};

export default ActiveTasksPanel;
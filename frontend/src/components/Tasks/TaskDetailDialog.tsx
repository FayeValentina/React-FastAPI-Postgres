import React, { useEffect, useState, useCallback } from 'react';
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
  Tabs,
  Tab,
  Grid,
  Card,
  CardContent,
  LinearProgress,
} from '@mui/material';
import {
  Close as CloseIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  HourglassEmpty as RunningIcon,
  Timelapse as TimeoutIcon,
  Info as InfoIcon,
  Settings as SettingsIcon,
  Timeline as TimelineIcon,
  Assessment as StatsIcon,
  BarChart as AssessmentIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { 
  JobDetailResponse, 
  ScheduleEvent, 
  EnhancedSchedule 
} from '../../types/task';

interface TaskDetailDialogProps {
  open: boolean;
  jobId: string | null;
  jobName: string;
  schedule?: EnhancedSchedule;
  onClose: () => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index, ...other }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`task-detail-tabpanel-${index}`}
      aria-labelledby={`task-detail-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 0 }}>{children}</Box>}
    </div>
  );
}

const TaskDetailDialog: React.FC<TaskDetailDialogProps> = ({
  open,
  jobId,
  jobName,
  schedule,
  onClose,
}) => {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));
  const { fetchData, getApiState } = useApiStore();
  
  const [tabValue, setTabValue] = useState(0);
  const [jobDetail, setJobDetail] = useState<JobDetailResponse | null>(null);
  const [recentEvents, setRecentEvents] = useState<ScheduleEvent[]>([]);
  
  const jobDetailUrl = jobId ? `/v1/tasks/jobs/${jobId}?hours=72&events_limit=20` : '';
  const eventsUrl = jobId ? `/v1/tasks/events?job_id=${jobId}&limit=50` : '';
  
  const { loading: detailLoading, error: detailError } = getApiState(jobDetailUrl);
  const { loading: eventsLoading, error: eventsError } = getApiState(eventsUrl);

  useEffect(() => {
    if (open && jobId) {
      loadData();
    }
  }, [open, jobId, loadData]);

  const loadData = useCallback(async () => {
    if (!jobId) return;
    
    try {
      const [detailData, eventsData] = await Promise.all([
        fetchData<JobDetailResponse>(jobDetailUrl),
        fetchData<ScheduleEvent[]>(eventsUrl),
      ]);
      
      setJobDetail(detailData);
      setRecentEvents(eventsData || []);
    } catch (error) {
      console.error('Failed to load task detail:', error);
    }
  }, [jobId, jobDetailUrl, eventsUrl, fetchData]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
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

  const getEventTypeColor = (eventType: string) => {
    switch (eventType.toLowerCase()) {
      case 'job_executed': return 'success';
      case 'job_error': return 'error';
      case 'job_missed': return 'warning';
      case 'job_added': return 'info';
      case 'job_removed': return 'default';
      default: return 'default';
    }
  };

  const renderBasicInfo = () => {
    const summary = schedule?.execution_summary;
    
    return (
      <Box>
        {/* Task Basic Information */}
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              <InfoIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
              基本信息
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">任务ID</Typography>
                <Typography variant="body1">{jobId}</Typography>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">任务名称</Typography>
                <Typography variant="body1">{jobName}</Typography>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">触发器</Typography>
                <Typography variant="body1">{schedule?.trigger || '-'}</Typography>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">下次运行</Typography>
                <Typography variant="body1">
                  {schedule?.next_run_time ? formatDateTime(schedule.next_run_time) : '未安排'}
                </Typography>
              </Grid>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">状态</Typography>
                <Chip
                  label={schedule?.computed_status || 'unknown'}
                  color={
                    schedule?.computed_status === 'running' ? 'primary' :
                    schedule?.computed_status === 'failed' ? 'error' :
                    schedule?.computed_status === 'paused' ? 'warning' : 'default'
                  }
                  size="small"
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <Typography variant="body2" color="text.secondary">是否挂起</Typography>
                <Typography variant="body1">{schedule?.pending ? '是' : '否'}</Typography>
              </Grid>
            </Grid>
          </CardContent>
        </Card>

        {/* Execution Summary */}
        {summary && (
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <StatsIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                执行摘要
              </Typography>
              <Grid container spacing={3}>
                <Grid item xs={6} sm={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="primary">{summary.total_runs}</Typography>
                    <Typography variant="caption" color="text.secondary">总执行次数</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="success.main">{summary.successful_runs}</Typography>
                    <Typography variant="caption" color="text.secondary">成功次数</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="error.main">{summary.failed_runs}</Typography>
                    <Typography variant="caption" color="text.secondary">失败次数</Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={3}>
                  <Box textAlign="center">
                    <Typography variant="h4">{summary.success_rate.toFixed(1)}%</Typography>
                    <Typography variant="caption" color="text.secondary">成功率</Typography>
                  </Box>
                </Grid>
              </Grid>
              
              <Box sx={{ mt: 3 }}>
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  成功率: {summary.success_rate.toFixed(1)}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={summary.success_rate}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>

              <Grid container spacing={2} sx={{ mt: 2 }}>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">平均耗时</Typography>
                  <Typography variant="body1">{formatDuration(summary.avg_duration)}</Typography>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <Typography variant="body2" color="text.secondary">最后执行</Typography>
                  <Typography variant="body1">
                    {summary.last_run ? formatDateTime(summary.last_run) : '从未执行'}
                  </Typography>
                </Grid>
                {summary.last_error && (
                  <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary">最后错误</Typography>
                    <Typography variant="body2" color="error.main">
                      {summary.last_error}
                    </Typography>
                  </Grid>
                )}
              </Grid>
            </CardContent>
          </Card>
        )}
      </Box>
    );
  };

  const renderExecutionHistory = () => {
    if (detailLoading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      );
    }

    if (detailError) {
      return (
        <Alert severity="error">
          加载执行历史失败
        </Alert>
      );
    }

    const executions = jobDetail?.execution_history || [];

    if (executions.length === 0) {
      return (
        <Alert severity="info">
          暂无执行历史
        </Alert>
      );
    }

    return (
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
                    color={
                      execution.status === 'success' ? 'success' : 
                      execution.status === 'failed' ? 'error' : 'default'
                    }
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
    );
  };

  const renderRecentEvents = () => {
    if (eventsLoading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      );
    }

    if (eventsError) {
      return (
        <Alert severity="error">
          加载事件历史失败
        </Alert>
      );
    }

    if (recentEvents.length === 0) {
      return (
        <Alert severity="info">
          暂无事件记录
        </Alert>
      );
    }

    return (
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>事件类型</TableCell>
              <TableCell>时间</TableCell>
              <TableCell>结果</TableCell>
              <TableCell>错误信息</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {recentEvents.map((event) => (
              <TableRow key={event.id}>
                <TableCell>
                  <Chip
                    label={event.event_type}
                    size="small"
                    color={getEventTypeColor(event.event_type) as 'success' | 'error' | 'warning' | 'info' | 'default'}
                  />
                </TableCell>
                <TableCell>{formatDateTime(event.created_at)}</TableCell>
                <TableCell>
                  {event.result && Object.keys(event.result).length > 0 ? (
                    <Typography variant="caption">
                      {JSON.stringify(event.result, null, 2).substring(0, 100)}...
                    </Typography>
                  ) : '-'}
                </TableCell>
                <TableCell>
                  {event.error_message && (
                    <Typography variant="caption" color="error">
                      {event.error_message}
                    </Typography>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  const renderConfiguration = () => {
    if (!schedule) {
      return (
        <Alert severity="info">
          暂无配置信息
        </Alert>
      );
    }

    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            <SettingsIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            任务配置
          </Typography>
          <Box component="pre" sx={{ 
            bgcolor: 'grey.100', 
            p: 2, 
            borderRadius: 1, 
            overflow: 'auto',
            fontSize: '0.875rem',
            fontFamily: 'monospace'
          }}>
            {JSON.stringify(schedule.config, null, 2)}
          </Box>
        </CardContent>
      </Card>
    );
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
          任务详情 - {jobName}
        </Typography>
        <IconButton onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 0 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange} aria-label="task detail tabs">
            <Tab label="基本信息" icon={<InfoIcon />} />
            <Tab label="执行历史" icon={<TimelineIcon />} />
            <Tab label="事件记录" icon={<AssessmentIcon />} />
            <Tab label="任务配置" icon={<SettingsIcon />} />
          </Tabs>
        </Box>
        
        <Box sx={{ p: 3 }}>
          <TabPanel value={tabValue} index={0}>
            {renderBasicInfo()}
          </TabPanel>
          <TabPanel value={tabValue} index={1}>
            {renderExecutionHistory()}
          </TabPanel>
          <TabPanel value={tabValue} index={2}>
            {renderRecentEvents()}
          </TabPanel>
          <TabPanel value={tabValue} index={3}>
            {renderConfiguration()}
          </TabPanel>
        </Box>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} variant="contained">
          关闭
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TaskDetailDialog;
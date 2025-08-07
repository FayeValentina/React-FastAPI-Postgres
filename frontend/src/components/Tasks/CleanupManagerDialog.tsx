import React, { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Tabs,
  Tab,
  TextField,
  FormControl,
  Alert,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Paper,
  IconButton,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Grid,
  Card,
  CardContent,
  CardHeader,
  LinearProgress,
} from '@mui/material';
import {
  Close as CloseIcon,
  CleaningServices as CleanupIcon,
  PlayArrow as TriggerIcon,
  Schedule as ScheduleIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  History as HistoryIcon,
  CheckCircle as SuccessIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { CleanupConfig } from '../../types/task';

interface CleanupManagerDialogProps {
  open: boolean;
  onClose: () => void;
  onCleanupComplete?: () => void;
}

interface CleanupSchedule {
  id: string;
  name: string;
  cron_expression: string;
  days_old: number;
  enabled: boolean;
  last_run?: string;
  next_run?: string;
}

interface CleanupHistory {
  id: string;
  started_at: string;
  completed_at: string;
  status: 'success' | 'failed' | 'running';
  deleted_records: number;
  error_message?: string;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`cleanup-tabpanel-${index}`}
      aria-labelledby={`cleanup-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
}

const CleanupManagerDialog: React.FC<CleanupManagerDialogProps> = ({
  open,
  onClose,
  onCleanupComplete,
}) => {
  const { postData, getApiState } = useApiStore();
  
  const [tabValue, setTabValue] = useState(0);
  const [activeStep, setActiveStep] = useState(0);
  const [cleanupInProgress, setCleanupInProgress] = useState(false);
  const [cleanupSchedules, setCleanupSchedules] = useState<CleanupSchedule[]>([]);
  const [cleanupHistory, setCleanupHistory] = useState<CleanupHistory[]>([]);
  
  // 清理配置表单状态
  const [cleanupForm, setCleanupForm] = useState({
    action: 'trigger' as 'trigger' | 'create' | 'update',
    days_old: 30,
    cron_expression: '0 2 * * 0', // 每周日凌晨2点
    schedule_id: '',
    schedule_name: '',
  });

  const cleanupUrl = '/v1/tasks/cleanup';
  getApiState(cleanupUrl);

  const loadCleanupData = useCallback(async () => {
    try {
      // 模拟加载清理调度和历史记录
      // 实际应用中需要调用对应的API端点
      const schedulesData: CleanupSchedule[] = [
        {
          id: 'weekly-cleanup',
          name: '每周清理',
          cron_expression: '0 2 * * 0',
          days_old: 30,
          enabled: true,
          last_run: '2025-01-01T02:00:00Z',
          next_run: '2025-01-08T02:00:00Z',
        },
        {
          id: 'monthly-cleanup',
          name: '每月清理',
          cron_expression: '0 1 1 * *',
          days_old: 90,
          enabled: false,
          last_run: '2024-12-01T01:00:00Z',
          next_run: '2025-02-01T01:00:00Z',
        },
      ];

      const historyData: CleanupHistory[] = [
        {
          id: 'cleanup-001',
          started_at: '2025-01-01T02:00:00Z',
          completed_at: '2025-01-01T02:15:00Z',
          status: 'success',
          deleted_records: 1250,
        },
        {
          id: 'cleanup-002',
          started_at: '2024-12-25T02:00:00Z',
          completed_at: '2024-12-25T02:12:00Z',
          status: 'success',
          deleted_records: 980,
        },
        {
          id: 'cleanup-003',
          started_at: '2024-12-18T02:00:00Z',
          completed_at: '2024-12-18T02:05:00Z',
          status: 'failed',
          deleted_records: 0,
          error_message: 'Database connection timeout',
        },
      ];

      setCleanupSchedules(schedulesData);
      setCleanupHistory(historyData);
    } catch (error) {
      console.error('Failed to load cleanup data:', error);
    }
  }, []);

  useEffect(() => {
    if (open) {
      loadCleanupData();
    }
  }, [open, loadCleanupData]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
    setActiveStep(0); // 重置步骤
  };

  const handleTriggerCleanup = async () => {
    setCleanupInProgress(true);
    try {
      const config: CleanupConfig = {
        action: 'trigger',
        days_old: cleanupForm.days_old,
      };
      
      await postData(cleanupUrl, config);
      setActiveStep(1);
      
      // 模拟清理进度
      setTimeout(() => {
        setActiveStep(2);
        setCleanupInProgress(false);
        onCleanupComplete?.();
      }, 3000);
      
    } catch (error) {
      console.error('Failed to trigger cleanup:', error);
      setCleanupInProgress(false);
    }
  };

  const handleCreateSchedule = async () => {
    try {
      const config: CleanupConfig = {
        action: 'create',
        days_old: cleanupForm.days_old,
        cron_expression: cleanupForm.cron_expression,
      };
      
      await postData(cleanupUrl, config);
      await loadCleanupData();
    } catch (error) {
      console.error('Failed to create cleanup schedule:', error);
    }
  };

  const handleDeleteSchedule = async (scheduleId: string) => {
    try {
      const config: CleanupConfig = {
        action: 'remove',
        schedule_id: scheduleId,
      };
      
      await postData(cleanupUrl, config);
      await loadCleanupData();
    } catch (error) {
      console.error('Failed to delete cleanup schedule:', error);
    }
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  const formatDuration = (startTime: string, endTime: string) => {
    const start = new Date(startTime);
    const end = new Date(endTime);
    const diffMs = end.getTime() - start.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffSeconds = Math.floor((diffMs % (1000 * 60)) / 1000);
    return `${diffMinutes}分${diffSeconds}秒`;
  };

  const renderManualCleanup = () => {

    return (
      <Box>
        <Stepper activeStep={activeStep} orientation="vertical">
          <Step>
            <StepLabel>配置清理参数</StepLabel>
            <StepContent>
              <Paper sx={{ p: 2, mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  清理设置
                </Typography>
                <FormControl fullWidth sx={{ mb: 2 }}>
                  <TextField
                    label="保留天数"
                    type="number"
                    value={cleanupForm.days_old}
                    onChange={(e) => setCleanupForm(prev => ({ 
                      ...prev, 
                      days_old: parseInt(e.target.value) || 30 
                    }))}
                    helperText="删除超过指定天数的执行记录和事件日志"
                    InputProps={{ inputProps: { min: 1, max: 365 } }}
                  />
                </FormControl>
                <Alert severity="warning" sx={{ mb: 2 }}>
                  此操作将永久删除超过 {cleanupForm.days_old} 天的历史数据，请谨慎操作！
                </Alert>
              </Paper>
              <Box>
                <Button
                  variant="contained"
                  startIcon={<TriggerIcon />}
                  onClick={handleTriggerCleanup}
                  disabled={cleanupInProgress}
                >
                  开始清理
                </Button>
              </Box>
            </StepContent>
          </Step>
          
          <Step>
            <StepLabel>执行清理操作</StepLabel>
            <StepContent>
              <Paper sx={{ p: 2, mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <CircularProgress size={20} sx={{ mr: 1 }} />
                  <Typography>正在清理历史数据...</Typography>
                </Box>
                <LinearProgress />
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  正在删除超过 {cleanupForm.days_old} 天的执行记录
                </Typography>
              </Paper>
            </StepContent>
          </Step>
          
          <Step>
            <StepLabel>清理完成</StepLabel>
            <StepContent>
              <Paper sx={{ p: 2, mb: 2 }}>
                <Alert severity="success" sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <SuccessIcon sx={{ mr: 1 }} />
                    清理操作已成功完成！
                  </Box>
                </Alert>
                <Typography variant="body2">
                  • 已删除 1,250 条执行记录
                </Typography>
                <Typography variant="body2">
                  • 已删除 3,420 条事件日志
                </Typography>
                <Typography variant="body2">
                  • 释放磁盘空间约 15.2 MB
                </Typography>
              </Paper>
              <Button onClick={() => setActiveStep(0)}>
                重新开始
              </Button>
            </StepContent>
          </Step>
        </Stepper>
      </Box>
    );
  };

  const renderScheduleManager = () => (
    <Box>
      {/* 创建新调度 */}
      <Card sx={{ mb: 3 }}>
        <CardHeader
          title="创建清理调度"
          avatar={<AddIcon />}
        />
        <CardContent>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="调度名称"
                value={cleanupForm.schedule_name}
                onChange={(e) => setCleanupForm(prev => ({ 
                  ...prev, 
                  schedule_name: e.target.value 
                }))}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="保留天数"
                type="number"
                value={cleanupForm.days_old}
                onChange={(e) => setCleanupForm(prev => ({ 
                  ...prev, 
                  days_old: parseInt(e.target.value) || 30 
                }))}
                InputProps={{ inputProps: { min: 1, max: 365 } }}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Cron 表达式"
                value={cleanupForm.cron_expression}
                onChange={(e) => setCleanupForm(prev => ({ 
                  ...prev, 
                  cron_expression: e.target.value 
                }))}
                helperText="例如: 0 2 * * 0 (每周日凌晨2点)"
              />
            </Grid>
            <Grid item xs={12}>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleCreateSchedule}
                disabled={!cleanupForm.schedule_name || !cleanupForm.cron_expression}
              >
                创建调度
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* 现有调度列表 */}
      <Card>
        <CardHeader
          title="清理调度列表"
          avatar={<ScheduleIcon />}
        />
        <CardContent>
          {cleanupSchedules.length === 0 ? (
            <Alert severity="info">
              暂无清理调度配置
            </Alert>
          ) : (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>名称</TableCell>
                    <TableCell>Cron 表达式</TableCell>
                    <TableCell>保留天数</TableCell>
                    <TableCell>状态</TableCell>
                    <TableCell>最后运行</TableCell>
                    <TableCell>下次运行</TableCell>
                    <TableCell align="right">操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {cleanupSchedules.map((schedule) => (
                    <TableRow key={schedule.id}>
                      <TableCell>{schedule.name}</TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                          {schedule.cron_expression}
                        </Typography>
                      </TableCell>
                      <TableCell>{schedule.days_old} 天</TableCell>
                      <TableCell>
                        <Chip
                          label={schedule.enabled ? '启用' : '禁用'}
                          color={schedule.enabled ? 'success' : 'default'}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        {schedule.last_run ? formatDateTime(schedule.last_run) : '-'}
                      </TableCell>
                      <TableCell>
                        {schedule.next_run ? formatDateTime(schedule.next_run) : '-'}
                      </TableCell>
                      <TableCell align="right">
                        <IconButton size="small" disabled>
                          <EditIcon fontSize="small" />
                        </IconButton>
                        <IconButton 
                          size="small" 
                          color="error"
                          onClick={() => handleDeleteSchedule(schedule.id)}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>
    </Box>
  );

  const renderCleanupHistory = () => (
    <Card>
      <CardHeader
        title="清理历史"
        avatar={<HistoryIcon />}
        subheader="最近的清理操作记录"
      />
      <CardContent>
        {cleanupHistory.length === 0 ? (
          <Alert severity="info">
            暂无清理历史记录
          </Alert>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>开始时间</TableCell>
                  <TableCell>结束时间</TableCell>
                  <TableCell>耗时</TableCell>
                  <TableCell>状态</TableCell>
                  <TableCell align="right">删除记录数</TableCell>
                  <TableCell>备注</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {cleanupHistory.map((record) => (
                  <TableRow key={record.id}>
                    <TableCell>{formatDateTime(record.started_at)}</TableCell>
                    <TableCell>
                      {record.completed_at ? formatDateTime(record.completed_at) : '-'}
                    </TableCell>
                    <TableCell>
                      {record.completed_at 
                        ? formatDuration(record.started_at, record.completed_at)
                        : '-'
                      }
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={record.status === 'success' ? '成功' : record.status === 'failed' ? '失败' : '运行中'}
                        color={
                          record.status === 'success' ? 'success' : 
                          record.status === 'failed' ? 'error' : 'primary'
                        }
                        size="small"
                      />
                    </TableCell>
                    <TableCell align="right">
                      {record.deleted_records.toLocaleString()}
                    </TableCell>
                    <TableCell>
                      {record.error_message && (
                        <Typography variant="caption" color="error">
                          {record.error_message}
                        </Typography>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </CardContent>
    </Card>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CleanupIcon />
          <Typography variant="h6">清理管理</Typography>
        </Box>
        <IconButton onClick={onClose}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 0 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange}>
            <Tab label="手动清理" icon={<TriggerIcon />} />
            <Tab label="调度管理" icon={<ScheduleIcon />} />
            <Tab label="清理历史" icon={<HistoryIcon />} />
          </Tabs>
        </Box>

        <Box sx={{ p: 3 }}>
          <TabPanel value={tabValue} index={0}>
            {renderManualCleanup()}
          </TabPanel>
          <TabPanel value={tabValue} index={1}>
            {renderScheduleManager()}
          </TabPanel>
          <TabPanel value={tabValue} index={2}>
            {renderCleanupHistory()}
          </TabPanel>
        </Box>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>关闭</Button>
      </DialogActions>
    </Dialog>
  );
};

export default CleanupManagerDialog;
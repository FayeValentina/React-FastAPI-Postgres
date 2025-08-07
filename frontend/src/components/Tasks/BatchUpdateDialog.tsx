import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Button,
  Typography,
  Box,
  Stepper,
  Step,
  StepLabel,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Checkbox,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Alert,
  Chip,
  IconButton,
  Grid,
  Card,
  CardContent,
  CardHeader,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Collapse,
} from '@mui/material';
import {
  Close as CloseIcon,
  Edit as BatchUpdateIcon,
  PlayArrow as ExecuteIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  ExpandLess,
  ExpandMore,
  Settings as SettingsIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { EnhancedSchedule, BatchUpdateConfig } from '../../types/task';

interface BatchUpdateDialogProps {
  open: boolean;
  onClose: () => void;
  schedules: EnhancedSchedule[];
  selectedScheduleIds: string[];
  onUpdateComplete?: () => void;
}

interface UpdateOperation {
  field: string;
  action: 'set' | 'modify' | 'enable' | 'disable';
  value: unknown;
  description: string;
}

interface BatchUpdateResult {
  schedule_id: string;
  schedule_name: string;
  status: 'success' | 'failed' | 'skipped';
  error_message?: string;
}

const BatchUpdateDialog: React.FC<BatchUpdateDialogProps> = ({
  open,
  onClose,
  schedules,
  selectedScheduleIds,
  onUpdateComplete,
}) => {
  const { postData } = useApiStore();
  
  const [activeStep, setActiveStep] = useState(0);
  const [selectedSchedules, setSelectedSchedules] = useState<EnhancedSchedule[]>([]);
  const [updateOperations, setUpdateOperations] = useState<UpdateOperation[]>([]);
  const [batchResults, setBatchResults] = useState<BatchUpdateResult[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [expandedOperations, setExpandedOperations] = useState<number[]>([]);

  // 更新操作表单状态
  const [updateForm, setUpdateForm] = useState({
    operation_type: '',
    target_field: '',
    new_value: '',
    cron_expression: '',
    trigger_type: '',
    enable_state: true,
  });

  useEffect(() => {
    if (open) {
      // 根据选中的ID筛选调度
      const selected = schedules.filter(schedule => 
        selectedScheduleIds.includes(schedule.schedule_id)
      );
      setSelectedSchedules(selected);
      setActiveStep(0);
      setUpdateOperations([]);
      setBatchResults([]);
    }
  }, [open, schedules, selectedScheduleIds]);

  const handleNext = () => {
    setActiveStep((prevStep) => prevStep + 1);
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const handleAddOperation = () => {
    if (!updateForm.operation_type) return;

    const operation: UpdateOperation = {
      field: updateForm.target_field,
      action: updateForm.operation_type as 'set' | 'modify' | 'enable' | 'disable',
      value: getOperationValue(),
      description: getOperationDescription(),
    };

    setUpdateOperations(prev => [...prev, operation]);
    
    // 重置表单
    setUpdateForm({
      operation_type: '',
      target_field: '',
      new_value: '',
      cron_expression: '',
      trigger_type: '',
      enable_state: true,
    });
  };

  const handleRemoveOperation = (index: number) => {
    setUpdateOperations(prev => prev.filter((_, i) => i !== index));
  };

  const handleExecuteBatchUpdate = async () => {
    setIsExecuting(true);
    const results: BatchUpdateResult[] = [];

    try {
      // 构建批量更新配置
      const batchConfig: BatchUpdateConfig = {
        schedule_ids: selectedScheduleIds,
        updates: updateOperations.reduce((acc, op) => {
          acc[op.field] = op.value;
          return acc;
        }, {} as Record<string, unknown>),
      };

      // 执行批量更新
      await postData('/v1/tasks/schedules/batch-update', batchConfig);

      // 模拟结果（实际应用中应该从API返回）
      selectedSchedules.forEach(schedule => {
        results.push({
          schedule_id: schedule.schedule_id,
          schedule_name: schedule.name,
          status: 'success',
        });
      });

      setBatchResults(results);
      handleNext();
      onUpdateComplete?.();
      
    } catch (error: unknown) {
      console.error('Batch update failed:', error);
      
      // 处理失败情况
      selectedSchedules.forEach(schedule => {
        results.push({
          schedule_id: schedule.schedule_id,
          schedule_name: schedule.name,
          status: 'failed',
          error_message: error instanceof Error ? error.message : '更新失败',
        });
      });
      
      setBatchResults(results);
      handleNext();
    } finally {
      setIsExecuting(false);
    }
  };

  const getOperationValue = () => {
    switch (updateForm.operation_type) {
      case 'set':
        if (updateForm.target_field === 'trigger') {
          return { type: updateForm.trigger_type, cron: updateForm.cron_expression };
        }
        return updateForm.new_value;
      case 'enable':
        return true;
      case 'disable':
        return false;
      default:
        return updateForm.new_value;
    }
  };

  const getOperationDescription = () => {
    switch (updateForm.operation_type) {
      case 'set':
        if (updateForm.target_field === 'trigger') {
          return `设置触发器为 ${updateForm.trigger_type}: ${updateForm.cron_expression}`;
        }
        return `设置 ${updateForm.target_field} 为 ${updateForm.new_value}`;
      case 'enable':
        return '启用选中的调度任务';
      case 'disable':
        return '禁用选中的调度任务';
      default:
        return `${updateForm.operation_type} ${updateForm.target_field}`;
    }
  };

  const toggleOperationExpanded = (index: number) => {
    setExpandedOperations(prev =>
      prev.includes(index)
        ? prev.filter(i => i !== index)
        : [...prev, index]
    );
  };

  const renderScheduleSelection = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        选择要更新的调度任务
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        已选中 {selectedSchedules.length} 个调度任务进行批量更新
      </Typography>
      
      <TableContainer component={Paper} sx={{ mt: 2 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox checked disabled />
              </TableCell>
              <TableCell>任务名称</TableCell>
              <TableCell>触发器</TableCell>
              <TableCell>状态</TableCell>
              <TableCell>下次运行</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {selectedSchedules.map((schedule) => (
              <TableRow key={schedule.schedule_id}>
                <TableCell padding="checkbox">
                  <Checkbox checked disabled />
                </TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
                    {schedule.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    ID: {schedule.schedule_id}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                    {schedule.trigger}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={schedule.computed_status || 'unknown'}
                    color={
                      schedule.computed_status === 'running' ? 'success' :
                      schedule.computed_status === 'failed' ? 'error' :
                      schedule.computed_status === 'paused' ? 'warning' : 'default'
                    }
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  {schedule.next_run_time 
                    ? new Date(schedule.next_run_time).toLocaleString('zh-CN')
                    : '未安排'
                  }
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Box sx={{ mt: 2 }}>
        <Button variant="contained" onClick={handleNext} disabled={selectedSchedules.length === 0}>
          下一步：配置更新操作
        </Button>
      </Box>
    </Box>
  );

  const renderOperationConfig = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        配置更新操作
      </Typography>
      
      {/* 添加操作表单 */}
      <Card sx={{ mb: 3 }}>
        <CardHeader title="添加更新操作" avatar={<SettingsIcon />} />
        <CardContent>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>操作类型</InputLabel>
                <Select
                  value={updateForm.operation_type}
                  label="操作类型"
                  onChange={(e) => setUpdateForm(prev => ({ 
                    ...prev, 
                    operation_type: e.target.value 
                  }))}
                >
                  <MenuItem value="set">设置值</MenuItem>
                  <MenuItem value="enable">启用任务</MenuItem>
                  <MenuItem value="disable">禁用任务</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            {updateForm.operation_type === 'set' && (
              <>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth>
                    <InputLabel>目标字段</InputLabel>
                    <Select
                      value={updateForm.target_field}
                      label="目标字段"
                      onChange={(e) => setUpdateForm(prev => ({ 
                        ...prev, 
                        target_field: e.target.value 
                      }))}
                    >
                      <MenuItem value="trigger">触发器</MenuItem>
                      <MenuItem value="max_instances">最大实例数</MenuItem>
                      <MenuItem value="timeout">超时时间</MenuItem>
                      <MenuItem value="retry_count">重试次数</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                {updateForm.target_field === 'trigger' ? (
                  <>
                    <Grid item xs={12} sm={6}>
                      <FormControl fullWidth>
                        <InputLabel>触发器类型</InputLabel>
                        <Select
                          value={updateForm.trigger_type}
                          label="触发器类型"
                          onChange={(e) => setUpdateForm(prev => ({ 
                            ...prev, 
                            trigger_type: e.target.value 
                          }))}
                        >
                          <MenuItem value="cron">Cron表达式</MenuItem>
                          <MenuItem value="interval">固定间隔</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Cron表达式"
                        value={updateForm.cron_expression}
                        onChange={(e) => setUpdateForm(prev => ({ 
                          ...prev, 
                          cron_expression: e.target.value 
                        }))}
                        placeholder="0 */2 * * *"
                        helperText="例如: 0 */2 * * * (每2小时执行一次)"
                      />
                    </Grid>
                  </>
                ) : (
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="新值"
                      value={updateForm.new_value}
                      onChange={(e) => setUpdateForm(prev => ({ 
                        ...prev, 
                        new_value: e.target.value 
                      }))}
                      type={updateForm.target_field.includes('timeout') || updateForm.target_field.includes('count') || updateForm.target_field.includes('instances') ? 'number' : 'text'}
                    />
                  </Grid>
                )}
              </>
            )}

            <Grid item xs={12}>
              <Button
                variant="outlined"
                startIcon={<SettingsIcon />}
                onClick={handleAddOperation}
                disabled={
                  !updateForm.operation_type ||
                  (updateForm.operation_type === 'set' && !updateForm.target_field) ||
                  (updateForm.operation_type === 'set' && updateForm.target_field === 'trigger' && (!updateForm.trigger_type || !updateForm.cron_expression)) ||
                  (updateForm.operation_type === 'set' && updateForm.target_field !== 'trigger' && !updateForm.new_value)
                }
              >
                添加操作
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* 操作列表 */}
      <Card>
        <CardHeader title="更新操作列表" avatar={<InfoIcon />} />
        <CardContent>
          {updateOperations.length === 0 ? (
            <Alert severity="info">
              请至少添加一个更新操作
            </Alert>
          ) : (
            <List>
              {updateOperations.map((operation, index) => (
                <React.Fragment key={index}>
                  <ListItem
                    secondaryAction={
                      <IconButton 
                        edge="end" 
                        color="error" 
                        onClick={() => handleRemoveOperation(index)}
                      >
                        <CloseIcon />
                      </IconButton>
                    }
                  >
                    <ListItemIcon>
                      <SettingsIcon />
                    </ListItemIcon>
                    <ListItemText
                      primary={operation.description}
                      secondary={`字段: ${operation.field} | 操作: ${operation.action}`}
                    />
                    <IconButton onClick={() => toggleOperationExpanded(index)}>
                      {expandedOperations.includes(index) ? <ExpandLess /> : <ExpandMore />}
                    </IconButton>
                  </ListItem>
                  
                  <Collapse in={expandedOperations.includes(index)} timeout="auto" unmountOnExit>
                    <Box sx={{ pl: 4, pr: 2, pb: 2 }}>
                      <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                        <Typography variant="caption" color="text.secondary">
                          操作详情:
                        </Typography>
                        <Box component="pre" sx={{ 
                          fontSize: '0.75rem',
                          fontFamily: 'monospace',
                          mt: 1,
                          overflow: 'auto'
                        }}>
                          {JSON.stringify({
                            field: operation.field,
                            action: operation.action,
                            value: operation.value
                          }, null, 2)}
                        </Box>
                      </Paper>
                    </Box>
                  </Collapse>
                  
                  {index < updateOperations.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          )}
        </CardContent>
      </Card>

      <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
        <Button onClick={handleBack}>
          上一步
        </Button>
        <Button 
          variant="contained" 
          onClick={handleNext}
          disabled={updateOperations.length === 0}
        >
          下一步：预览更改
        </Button>
      </Box>
    </Box>
  );

  const renderPreview = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        预览更改
      </Typography>
      <Typography variant="body2" color="text.secondary" gutterBottom>
        请确认以下更改将应用到 {selectedSchedules.length} 个调度任务
      </Typography>

      <Alert severity="warning" sx={{ mb: 3 }}>
        <Typography variant="subtitle2">注意事项:</Typography>
        <Typography variant="body2">
          • 更改将立即生效，无法撤销
        </Typography>
        <Typography variant="body2">
          • 正在运行的任务不会受到影响
        </Typography>
        <Typography variant="body2">
          • 请确保更改符合预期
        </Typography>
      </Alert>

      {/* 影响的任务 */}
      <Card sx={{ mb: 3 }}>
        <CardHeader title="影响的任务" />
        <CardContent>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {selectedSchedules.map(schedule => (
              <Chip
                key={schedule.schedule_id}
                label={schedule.name}
                variant="outlined"
                size="small"
              />
            ))}
          </Box>
        </CardContent>
      </Card>

      {/* 将要执行的操作 */}
      <Card>
        <CardHeader title="执行的操作" />
        <CardContent>
          <List>
            {updateOperations.map((operation, index) => (
              <ListItem key={index}>
                <ListItemIcon>
                  <SettingsIcon color="primary" />
                </ListItemIcon>
                <ListItemText
                  primary={operation.description}
                  secondary={
                    <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                      {operation.field}: {JSON.stringify(operation.value)}
                    </Typography>
                  }
                />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>

      <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
        <Button onClick={handleBack}>
          上一步
        </Button>
        <Button
          variant="contained"
          color="primary"
          startIcon={<ExecuteIcon />}
          onClick={handleExecuteBatchUpdate}
          disabled={isExecuting}
        >
          {isExecuting ? '执行中...' : '执行批量更新'}
        </Button>
      </Box>
    </Box>
  );

  const renderResults = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        批量更新结果
      </Typography>

      <Box sx={{ mb: 3 }}>
        {batchResults.every(r => r.status === 'success') ? (
          <Alert severity="success">
            所有 {batchResults.length} 个任务已成功更新！
          </Alert>
        ) : (
          <Alert severity="warning">
            {batchResults.filter(r => r.status === 'success').length} 个任务更新成功，
            {batchResults.filter(r => r.status === 'failed').length} 个任务更新失败
          </Alert>
        )}
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>任务名称</TableCell>
              <TableCell>任务ID</TableCell>
              <TableCell>状态</TableCell>
              <TableCell>错误信息</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {batchResults.map((result) => (
              <TableRow key={result.schedule_id}>
                <TableCell>{result.schedule_name}</TableCell>
                <TableCell>
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                    {result.schedule_id}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    icon={
                      result.status === 'success' ? <SuccessIcon /> :
                      result.status === 'failed' ? <ErrorIcon /> : <WarningIcon />
                    }
                    label={
                      result.status === 'success' ? '成功' :
                      result.status === 'failed' ? '失败' : '跳过'
                    }
                    color={
                      result.status === 'success' ? 'success' :
                      result.status === 'failed' ? 'error' : 'default'
                    }
                    size="small"
                  />
                </TableCell>
                <TableCell>
                  {result.error_message && (
                    <Typography variant="caption" color="error">
                      {result.error_message}
                    </Typography>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <Box sx={{ mt: 2 }}>
        <Button variant="contained" onClick={onClose}>
          完成
        </Button>
      </Box>
    </Box>
  );

  const steps = [
    '选择任务',
    '配置操作',
    '预览更改',
    '执行结果',
  ];

  const getStepContent = (step: number) => {
    switch (step) {
      case 0:
        return renderScheduleSelection();
      case 1:
        return renderOperationConfig();
      case 2:
        return renderPreview();
      case 3:
        return renderResults();
      default:
        return null;
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <BatchUpdateIcon />
          <Typography variant="h6">批量更新任务</Typography>
        </Box>
        <IconButton onClick={onClose} disabled={isExecuting}>
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        <Box sx={{ mb: 3 }}>
          <Stepper activeStep={activeStep}>
            {steps.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Box>

        {getStepContent(activeStep)}
      </DialogContent>
    </Dialog>
  );
};

export default BatchUpdateDialog;
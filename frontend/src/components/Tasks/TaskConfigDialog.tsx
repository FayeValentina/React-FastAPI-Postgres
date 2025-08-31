import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Typography,
  Divider,
} from '@mui/material';
import { TaskConfig, TaskConfigCreate, TaskConfigUpdate, SystemEnums } from '../../types/task';
import { useApiStore } from '../../stores/api-store';

interface TaskConfigDialogProps {
  open: boolean;
  config: TaskConfig | null;
  onClose: () => void;
  onSave: (data: TaskConfigCreate | TaskConfigUpdate) => void;
}

const TaskConfigDialog: React.FC<TaskConfigDialogProps> = ({
  open,
  config,
  onClose,
  onSave,
}) => {
  const { fetchData } = useApiStore();
  const [taskTypes, setTaskTypes] = useState<string[]>([]);
  const [formData, setFormData] = useState<TaskConfigCreate>({
    name: '',
    description: '',
    task_type: '',
    scheduler_type: 'manual',
    parameters: {},
    schedule_config: {},
    max_retries: 0,
    timeout_seconds: 300,
    priority: 5,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    // 加载系统枚举值
    fetchData<SystemEnums>('/v1/tasks/system/enums').then((data) => {
      setTaskTypes(data.task_types || []);
    });
  }, [fetchData]);

  useEffect(() => {
    if (config) {
      setFormData({
        name: config.name,
        description: config.description || '',
        task_type: config.task_type,
        scheduler_type: config.scheduler_type,
        parameters: config.parameters,
        schedule_config: config.schedule_config,
        max_retries: config.max_retries,
        timeout_seconds: config.timeout_seconds,
        priority: config.priority,
      });
    } else {
      setFormData({
        name: '',
        description: '',
        task_type: '',
        scheduler_type: 'manual',
        parameters: {},
        schedule_config: {},
        max_retries: 0,
        timeout_seconds: 300,
        priority: 5,
      });
    }
    setErrors({});
  }, [config]);

  const handleChange = (field: keyof TaskConfigCreate, value: unknown) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
    
    if (errors[field]) {
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.name.trim()) {
      newErrors.name = '请输入任务名称';
    }
    if (!formData.task_type) {
      newErrors.task_type = '请选择任务类型';
    }
    if (formData.scheduler_type === 'cron' && !formData.schedule_config.cron_expression) {
      newErrors.schedule_config = '请输入Cron表达式';
    }
    if (formData.scheduler_type === 'interval' && !formData.schedule_config.interval_seconds) {
      newErrors.schedule_config = '请输入间隔时间';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (!validate()) return;
    
    if (config) {
      // 更新时，过滤掉未修改的字段
      const updateData: TaskConfigUpdate = {};
      Object.keys(formData).forEach((key) => {
        const k = key as keyof TaskConfigCreate;
        if (formData[k] !== config[k as keyof TaskConfig]) {
          (updateData as Record<string, unknown>)[k] = formData[k];
        }
      });
      onSave(updateData);
    } else {
      onSave(formData);
    }
  };

  const renderScheduleConfig = () => {
    switch (formData.scheduler_type) {
      case 'cron':
        return (
          <TextField
            fullWidth
            label="Cron表达式"
            value={formData.schedule_config.cron_expression || ''}
            onChange={(e) => handleChange('schedule_config', { 
              ...formData.schedule_config, 
              cron_expression: e.target.value 
            })}
            error={!!errors.schedule_config}
            helperText={errors.schedule_config || '例如: 0 */2 * * * (每2小时)'}
          />
        );
        
      case 'interval':
        return (
          <TextField
            fullWidth
            label="间隔时间 (秒)"
            type="number"
            value={formData.schedule_config.interval_seconds || ''}
            onChange={(e) => handleChange('schedule_config', { 
              ...formData.schedule_config, 
              interval_seconds: parseInt(e.target.value) 
            })}
            error={!!errors.schedule_config}
            helperText={errors.schedule_config}
          />
        );
        
      case 'date':
        return (
          <TextField
            fullWidth
            label="运行时间"
            type="datetime-local"
            value={formData.schedule_config.run_date || ''}
            onChange={(e) => handleChange('schedule_config', { 
              ...formData.schedule_config, 
              run_date: e.target.value 
            })}
            InputLabelProps={{ shrink: true }}
          />
        );
        
      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {config ? '编辑任务配置' : '创建任务配置'}
      </DialogTitle>
      
      <DialogContent dividers>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom>
              基本信息
            </Typography>
            <Divider sx={{ mb: 2 }} />
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              label="任务名称"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              error={!!errors.name}
              helperText={errors.name}
              required
            />
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth required error={!!errors.task_type}>
              <InputLabel>任务类型</InputLabel>
              <Select
                value={formData.task_type}
                onChange={(e) => handleChange('task_type', e.target.value)}
                label="任务类型"
                disabled={!!config}
              >
                {taskTypes.map(type => (
                  <MenuItem key={type} value={type}>{type}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="描述"
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              multiline
              rows={2}
            />
          </Grid>
          
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom>
              调度设置
            </Typography>
            <Divider sx={{ mb: 2 }} />
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth>
              <InputLabel>调度类型</InputLabel>
              <Select
                value={formData.scheduler_type}
                onChange={(e) => handleChange('scheduler_type', e.target.value)}
                label="调度类型"
                disabled={!!config}
              >
                <MenuItem value="manual">手动</MenuItem>
                <MenuItem value="interval">间隔</MenuItem>
                <MenuItem value="cron">Cron</MenuItem>
                <MenuItem value="date">定时</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} sm={6}>
            {renderScheduleConfig()}
          </Grid>
          
          <Grid item xs={12}>
            <Typography variant="subtitle1" gutterBottom>
              高级设置
            </Typography>
            <Divider sx={{ mb: 2 }} />
          </Grid>
          
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              label="最大重试次数"
              type="number"
              value={formData.max_retries}
              onChange={(e) => handleChange('max_retries', parseInt(e.target.value))}
              inputProps={{ min: 0, max: 10 }}
            />
          </Grid>
          
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              label="超时时间 (秒)"
              type="number"
              value={formData.timeout_seconds}
              onChange={(e) => handleChange('timeout_seconds', parseInt(e.target.value))}
              inputProps={{ min: 1 }}
            />
          </Grid>
          
          <Grid item xs={12} sm={4}>
            <TextField
              fullWidth
              label="优先级"
              type="number"
              value={formData.priority}
              onChange={(e) => handleChange('priority', parseInt(e.target.value))}
              inputProps={{ min: 1, max: 10 }}
            />
          </Grid>
        </Grid>
      </DialogContent>
      
      <DialogActions>
        <Button onClick={onClose}>取消</Button>
        <Button onClick={handleSubmit} variant="contained">
          {config ? '更新' : '创建'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TaskConfigDialog;
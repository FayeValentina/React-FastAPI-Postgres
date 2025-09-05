import React, { useState, useEffect, useMemo } from 'react';
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
  Box,
  Collapse,
} from '@mui/material';
import { TaskConfig, TaskConfigCreate, TaskConfigUpdate, SystemEnums } from '../../types/task';
import { TaskInfoResponse, TaskParameterInfo } from '../../types/task-info';
import { isIgnoredParam, flattenOptional, pickWidget, parseDefault, coerceOnChange, isEmptyValue, jsonExampleForParamFromType } from '../../utils/task-params';
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
  const [paramErrors, setParamErrors] = useState<Record<string, string>>({});
  const [taskInfos, setTaskInfos] = useState<TaskInfoResponse | null>(null);
  const [exampleOpen, setExampleOpen] = useState<Record<string, boolean>>({});

  const toggleExample = (key: string) => {
    setExampleOpen((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const copyExample = async (text?: string) => {
    if (!text) return;
    try {
      await navigator.clipboard?.writeText(text);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    // 加载系统枚举值
    fetchData<SystemEnums>('/v1/tasks/system/enums').then((data) => {
      setTaskTypes(data.task_types || []);
    });
    // 加载任务参数元数据
    fetchData<TaskInfoResponse>('/v1/tasks/system/task-info').then((data) => {
      setTaskInfos(data);
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
    setParamErrors({});
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = () => {
    if (!validate()) return;

    // 参数必填校验
    const paramsOf = paramsMap[formData.task_type] || [];
    const newParamErrors: Record<string, string> = {};
    paramsOf.forEach((p) => {
      if (p.required && !isIgnoredParam(p)) {
        const val = (formData.parameters as Record<string, unknown>)[p.name];
        if (isEmptyValue(val)) {
          newParamErrors[p.name] = '必填项';
        }
      }
    });
    setParamErrors(newParamErrors);
    if (Object.keys(newParamErrors).length > 0) return;

    // 清洗参数：仅提交用户提供的非空值，并做必要的类型收敛（尤其 JSON）
    const cleanedParams: Record<string, unknown> = {};
    paramsOf.forEach((p) => {
      const baseType = flattenOptional(p.type_info);
      const widget = pickWidget(`${formData.task_type}.${p.name}`, baseType, p.ui);
      let val = (formData.parameters as Record<string, unknown>)[p.name];
      if (widget === 'json' && typeof val === 'string') {
        try { val = JSON.parse(val as string); } catch { /* keep string */ }
      }
      if (!isEmptyValue(val)) cleanedParams[p.name] = val;
    });

    if (config) {
      // 更新时，过滤掉未修改的字段
      const updateData: TaskConfigUpdate = {};
      Object.keys(formData).forEach((key) => {
        const k = key as keyof TaskConfigCreate;
        if (formData[k] !== config[k as keyof TaskConfig]) {
          (updateData as Record<string, unknown>)[k] = formData[k];
        }
      });
      // 覆盖 parameters 为清洗后的内容并判断是否变化
      const currentParams = config.parameters || {};
      const isParamsChanged = JSON.stringify(cleanedParams) !== JSON.stringify(currentParams);
      if (isParamsChanged) {
        (updateData as Record<string, unknown>)['parameters'] = cleanedParams;
      } else {
        delete (updateData as Record<string, unknown>)['parameters'];
      }
      onSave(updateData);
    } else {
      onSave({ ...formData, parameters: cleanedParams });
    }
  };

  const paramsMap: Record<string, TaskParameterInfo[]> = useMemo(() => {
    const map: Record<string, TaskParameterInfo[]> = {};
    taskInfos?.tasks.forEach((t) => {
      const filtered = (t.parameters || []).filter((p) => !isIgnoredParam(p));
      map[t.name] = filtered;
    });
    return map;
  }, [taskInfos]);

  const handleParamChange = (paramName: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      parameters: {
        ...prev.parameters,
        [paramName]: value,
      },
    }));
    if (paramErrors[paramName]) {
      setParamErrors((prev) => {
        const next = { ...prev };
        delete next[paramName];
        return next;
      });
    }
  };

  const renderTaskParameters = () => {
    if (!formData.task_type) return null;
    const params = paramsMap[formData.task_type] || [];
    if (params.length === 0) return null;

    return (
      <>
        <Grid item xs={12}>
          <Typography variant="subtitle1" gutterBottom>
            任务参数
          </Typography>
          <Divider sx={{ mb: 2 }} />
        </Grid>
        {params.map((p) => {
          const t = flattenOptional(p.type_info);
          const widget = pickWidget(`${formData.task_type}.${p.name}`, t, p.ui);
          const current = (formData.parameters as Record<string, unknown>)[p.name];
          const initial = parseDefault(p.default ?? null, t);
          const value = current ?? initial ?? (widget === 'boolean' ? false : '');
          const label = p.ui?.label || p.name;
          const helper = p.ui?.description;
          const commonProps = {
            fullWidth: true,
            label,
            error: !!paramErrors[p.name],
            helperText: paramErrors[p.name] || helper,
          } as const;

          if (widget === 'select') {
            return (
              <Grid item xs={12} sm={6} key={p.name}>
                <FormControl fullWidth error={!!paramErrors[p.name]}>
                  <InputLabel>{label}</InputLabel>
                  <Select
                    label={label}
                    value={(value as string) ?? ''}
                    onChange={(e) => handleParamChange(p.name, coerceOnChange(e.target.value, t))}
                  >
                    {(p.ui?.choices || []).map((opt, idx) => (
                      <MenuItem key={`${p.name}-${idx}`} value={opt}>
                        {String(opt)}
                      </MenuItem>
                    ))}
                  </Select>
                  {paramErrors[p.name] && (
                    <Typography color="error" variant="caption">
                      {paramErrors[p.name]}
                    </Typography>
                  )}
                </FormControl>
              </Grid>
            );
          }

          if (widget === 'boolean') {
            return (
              <Grid item xs={12} sm={6} key={p.name}>
                <FormControl fullWidth>
                  <Typography variant="body2" gutterBottom>{label}</Typography>
                  <Select
                    value={value ? 'true' : 'false'}
                    onChange={(e) => handleParamChange(p.name, e.target.value === 'true')}
                  >
                    <MenuItem value="true">是</MenuItem>
                    <MenuItem value="false">否</MenuItem>
                  </Select>
                  {helper && (
                    <Typography variant="caption" color="text.secondary">
                      {helper}
                    </Typography>
                  )}
                </FormControl>
              </Grid>
            );
          }

          if (widget === 'number') {
            return (
              <Grid item xs={12} sm={6} key={p.name}>
                <TextField
                  {...commonProps}
                  type="number"
                  value={value as number | string}
                  onChange={(e) => handleParamChange(p.name, coerceOnChange(e.target.value, t))}
                  inputProps={{
                    min: p.ui?.min,
                    max: p.ui?.max,
                    step: p.ui?.step,
                  }}
                />
              </Grid>
            );
          }

          if (widget === 'json') {
            const exampleData = p.ui?.example ?? undefined;
            const example = exampleData !== undefined
              ? (typeof exampleData === 'string' ? exampleData : JSON.stringify(exampleData, null, 2))
              : jsonExampleForParamFromType(t);
            const fqn = `${formData.task_type}.${p.name}`;
            const open = !!exampleOpen[fqn];
            return (
              <Grid item xs={12} key={p.name}>
                {example && (
                  <>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Typography variant="caption" color="text.secondary">示例</Typography>
                      <Button size="small" onClick={() => toggleExample(fqn)}>
                        {open ? '收起' : '展开'}
                      </Button>
                      <Button size="small" onClick={() => copyExample(example)}>复制</Button>
                    </Box>
                    <Collapse in={open} timeout="auto" unmountOnExit={false}>
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        component="pre"
                        sx={{ whiteSpace: 'pre-wrap', p: 1, bgcolor: 'action.hover', borderRadius: 1, mb: 1, fontFamily: 'monospace' }}
                      >
                        {example}
                      </Typography>
                    </Collapse>
                  </>
                )}
                <TextField
                  {...commonProps}
                  multiline
                  minRows={3}
                  value={typeof value === 'string' ? (value as string) : JSON.stringify(value ?? '', null, 2)}
                  onChange={(e) => handleParamChange(p.name, e.target.value)}
                  placeholder={p.ui?.placeholder || '输入 JSON'}
                />
              </Grid>
            );
          }

          // text / email
          return (
            <Grid item xs={12} sm={6} key={p.name}>
              <TextField
                {...commonProps}
                type={widget === 'email' ? 'email' : 'text'}
                value={String(value ?? '')}
                onChange={(e) => handleParamChange(p.name, coerceOnChange(e.target.value, t))}
                placeholder={p.ui?.placeholder}
                inputProps={{
                  pattern: p.ui?.pattern,
                }}
              />
            </Grid>
          );
        })}
      </>
    );
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

          {renderTaskParameters()}
          
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

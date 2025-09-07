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
  FormGroup,
  FormControlLabel,
  Checkbox,
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
  const [schedulerTypes, setSchedulerTypes] = useState<string[]>(['manual', 'cron', 'date']);
  // Cron 构造器状态
  const [cronMode, setCronMode] = useState<'builder' | 'expert'>('builder');
  const [cronFreq, setCronFreq] = useState<'minute' | 'hour' | 'day' | 'week' | 'month'>('day');
  const [everyNMinutes, setEveryNMinutes] = useState<number>(5);
  const [minuteOfHour, setMinuteOfHour] = useState<number>(0);
  const [hourOfDay, setHourOfDay] = useState<number>(3);
  const [minuteOfDay, setMinuteOfDay] = useState<number>(0);
  const [dayOfMonth, setDayOfMonth] = useState<number>(1);
  const [daysOfWeek, setDaysOfWeek] = useState<number[]>([1]); // 0=周日,1=周一

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
      if (Array.isArray(data.scheduler_types) && data.scheduler_types.length > 0) {
        setSchedulerTypes(data.scheduler_types);
      }
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

  // ------- Cron 构造器：初始化与同步 -------
  const initCronBuilderFromConfig = (sc: Record<string, unknown>) => {
    const getStr = (key: string, fallback = '*') => {
      const v = sc[key];
      return v === undefined || v === null ? fallback : String(v);
    };
    const minute = getStr('minute');
    const hour = getStr('hour');
    const day = getStr('day');
    const dow = getStr('day_of_week');
    const expr = typeof sc['cron_expression'] === 'string' ? (sc['cron_expression'] as string) : undefined;

    let m = minute, h = hour, d = day, w = dow;
    if (expr && expr.split(' ').length >= 5) {
      const parts = expr.trim().split(/\s+/).slice(0, 5);
      // parts: minute hour day month dow
      [m, h, d, , w] = parts as [string, string, string, string, string];
    }

    // 推断频率
    if (w !== '*') {
      setCronFreq('week');
      setDaysOfWeek(w.split(',').filter(Boolean).map((x) => Number(x)).filter((n) => !Number.isNaN(n)));
    } else if (d !== '*' && d !== '?') {
      setCronFreq('month');
      const dom = parseInt(d, 10);
      setDayOfMonth(Number.isNaN(dom) ? 1 : Math.min(31, Math.max(1, dom)));
    } else if (h !== '*') {
      setCronFreq('day');
    } else if (m.startsWith('*/')) {
      setCronFreq('minute');
      const n = parseInt(m.slice(2), 10);
      setEveryNMinutes(Number.isNaN(n) ? 5 : Math.min(59, Math.max(1, n)));
    } else {
      setCronFreq('hour');
    }

    // 数值部分
    const mh = parseInt(h, 10);
    const mm = parseInt(m, 10);
    if (!Number.isNaN(mh)) setHourOfDay(Math.min(23, Math.max(0, mh)));
    if (!Number.isNaN(mm)) {
      setMinuteOfHour(Math.min(59, Math.max(0, mm)));
      setMinuteOfDay(Math.min(59, Math.max(0, mm)));
    }
  };

  useEffect(() => {
    if (formData.scheduler_type === 'cron') {
      initCronBuilderFromConfig(formData.schedule_config || {});
      setCronMode('builder');
    }
  }, [formData.scheduler_type, formData.schedule_config]);

  const cronStringFromBuilder = () => {
    let minute = '*', hour = '*', day = '*', day_of_week = '*';
    const month = '*';
    switch (cronFreq) {
      case 'minute':
        minute = `*/${Math.min(59, Math.max(1, Number(everyNMinutes) || 1))}`;
        break;
      case 'hour':
        minute = String(Math.min(59, Math.max(0, Number(minuteOfHour) || 0)));
        break;
      case 'day':
        minute = String(Math.min(59, Math.max(0, Number(minuteOfDay) || 0)));
        hour = String(Math.min(23, Math.max(0, Number(hourOfDay) || 0)));
        break;
      case 'week':
        minute = String(Math.min(59, Math.max(0, Number(minuteOfDay) || 0)));
        hour = String(Math.min(23, Math.max(0, Number(hourOfDay) || 0)));
        day_of_week = daysOfWeek.length > 0 ? daysOfWeek.join(',') : '*';
        break;
      case 'month':
        minute = String(Math.min(59, Math.max(0, Number(minuteOfDay) || 0)));
        hour = String(Math.min(23, Math.max(0, Number(hourOfDay) || 0)));
        day = String(Math.min(31, Math.max(1, Number(dayOfMonth) || 1)));
        break;
    }
    return `${minute} ${hour} ${day} ${month} ${day_of_week}`;
  };

  const applyBuilderToScheduleConfig = () => {
    const [minute, hour, day, month, day_of_week] = cronStringFromBuilder().split(' ');
    const sc: Record<string, unknown> = { ...(formData.schedule_config || {}) };
    delete sc['cron_expression'];
    sc['minute'] = minute;
    sc['hour'] = hour;
    sc['day'] = day;
    sc['month'] = month;
    sc['day_of_week'] = day_of_week;
    handleChange('schedule_config', sc);
  };

  useEffect(() => {
    if (formData.scheduler_type === 'cron' && cronMode === 'builder') {
      applyBuilderToScheduleConfig();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cronFreq, everyNMinutes, minuteOfHour, hourOfDay, minuteOfDay, dayOfMonth, daysOfWeek, cronMode]);

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
    if (formData.scheduler_type === 'cron') {
      const sc: Record<string, unknown> = (formData.schedule_config || {});
      const hasExpr = typeof sc['cron_expression'] === 'string' && (sc['cron_expression'] as string).trim() !== '';
      const hasParts = ['minute', 'hour', 'day', 'month', 'day_of_week'].every((k) => sc[k] !== undefined);
      if (!hasExpr && !hasParts) {
        newErrors.schedule_config = '请使用构造器或输入Cron表达式';
      }
      if (cronMode === 'builder' && cronFreq === 'week' && daysOfWeek.length === 0) {
        newErrors.schedule_config = '请选择至少一个星期几';
      }
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
              <Grid item xs={12} key={p.name}>
                <FormControl fullWidth error={!!paramErrors[p.name]}>
                  <InputLabel>{label}</InputLabel>
                  <Select
                    label={label}
                    value={(value as string) ?? ''}
                    onChange={(e) => handleParamChange(p.name, coerceOnChange(e.target.value, t))}
                  >
                    {(p.ui?.choices || []).map((opt, idx) => (
                      <MenuItem key={`${p.name}-${idx}`} value={String(opt)}>
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
              <Grid item xs={12} key={p.name}>
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
              <Grid item xs={12} key={p.name}>
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
            <Grid item xs={12} key={p.name}>
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
      case 'cron': {
        const minutes = Array.from({ length: 60 }, (_, i) => i);
        const hours = Array.from({ length: 24 }, (_, i) => i);
        const days = Array.from({ length: 31 }, (_, i) => i + 1);
        const weekDays = [
          { v: 0, l: '周日' },
          { v: 1, l: '周一' },
          { v: 2, l: '周二' },
          { v: 3, l: '周三' },
          { v: 4, l: '周四' },
          { v: 5, l: '周五' },
          { v: 6, l: '周六' },
        ];
        const cronPreview: string = cronMode === 'builder'
          ? cronStringFromBuilder()
          : (typeof formData.schedule_config['cron_expression'] === 'string'
            ? (formData.schedule_config['cron_expression'] as string)
            : '');
        return (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button size="small" variant={cronMode === 'builder' ? 'contained' : 'outlined'} onClick={() => setCronMode('builder')}>向导</Button>
              <Button size="small" variant={cronMode === 'expert' ? 'contained' : 'outlined'} onClick={() => setCronMode('expert')}>高级</Button>
            </Box>
            {cronMode === 'builder' ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <FormControl fullWidth>
                  <InputLabel>任务频率</InputLabel>
                  <Select
                    label="任务频率"
                    value={cronFreq}
                    onChange={(e) => {
                      const v = e.target.value;
                      if (v === 'minute' || v === 'hour' || v === 'day' || v === 'week' || v === 'month') {
                        setCronFreq(v);
                      }
                    }}
                  >
                    <MenuItem value="minute">每分钟</MenuItem>
                    <MenuItem value="hour">每小时</MenuItem>
                    <MenuItem value="day">每天</MenuItem>
                    <MenuItem value="week">每周</MenuItem>
                    <MenuItem value="month">每月</MenuItem>
                  </Select>
                </FormControl>
                {cronFreq === 'minute' && (
                  <TextField
                    label="每隔 N 分钟"
                    type="number"
                    inputProps={{ min: 1, max: 59 }}
                    value={everyNMinutes}
                    onChange={(e) => setEveryNMinutes(parseInt(e.target.value || '1', 10))}
                  />
                )}
                {cronFreq === 'hour' && (
                  <FormControl fullWidth>
                    <InputLabel>每小时的第几分钟</InputLabel>
                    <Select label="每小时的第几分钟" value={minuteOfHour} onChange={(e) => setMinuteOfHour(Number(e.target.value))}>
                      {minutes.map((m) => (
                        <MenuItem key={m} value={m}>{m.toString().padStart(2, '0')}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                )}
                {(cronFreq === 'day' || cronFreq === 'week' || cronFreq === 'month') && (
                  <Box sx={{ display: 'flex', gap: 2 }}>
                    <FormControl fullWidth>
                      <InputLabel>小时</InputLabel>
                      <Select label="小时" value={hourOfDay} onChange={(e) => setHourOfDay(Number(e.target.value))}>
                        {hours.map((h) => (
                          <MenuItem key={h} value={h}>{h.toString().padStart(2, '0')}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                    <FormControl fullWidth>
                      <InputLabel>分钟</InputLabel>
                      <Select label="分钟" value={minuteOfDay} onChange={(e) => setMinuteOfDay(Number(e.target.value))}>
                        {minutes.map((m) => (
                          <MenuItem key={m} value={m}>{m.toString().padStart(2, '0')}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Box>
                )}
                {cronFreq === 'week' && (
                  <FormGroup>
                    <Typography variant="body2" sx={{ mb: 1 }}>每周的：</Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap' }}>
                      {weekDays.map((d) => (
                        <FormControlLabel
                          key={d.v}
                          control={
                            <Checkbox
                              checked={daysOfWeek.includes(d.v)}
                              onChange={(e) => {
                                const checked = e.target.checked;
                                setDaysOfWeek((prev) => {
                                  const set = new Set(prev);
                                  if (checked) set.add(d.v); else set.delete(d.v);
                                  return Array.from(set).sort((a, b) => a - b);
                                });
                              }}
                            />
                          }
                          label={d.l}
                        />
                      ))}
                    </Box>
                  </FormGroup>
                )}
                {cronFreq === 'month' && (
                  <FormControl fullWidth>
                    <InputLabel>每月的第几天</InputLabel>
                    <Select label="每月的第几天" value={dayOfMonth} onChange={(e) => setDayOfMonth(Number(e.target.value))}>
                      {days.map((d) => (
                        <MenuItem key={d} value={d}>{d}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                )}
                <Typography variant="caption" color="text.secondary">预览: {cronPreview}</Typography>
                {errors.schedule_config && (
                  <Typography variant="caption" color="error">{errors.schedule_config}</Typography>
                )}
              </Box>
            ) : (
              <TextField
                fullWidth
                label="Cron表达式"
                value={formData.schedule_config.cron_expression || ''}
                onChange={(e) => handleChange('schedule_config', { ...formData.schedule_config, cron_expression: e.target.value })}
                placeholder="例如: 0 3 * * * (每天 03:00)"
                error={!!errors.schedule_config}
                helperText={errors.schedule_config || '支持标准5段式 Cron (分 时 日 月 周)'}
              />
            )}
          </Box>
        );
      }
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
                {schedulerTypes.map((t) => (
                  <MenuItem key={t} value={t}>
                    {t === 'manual' ? '手动' : t === 'cron' ? 'Cron' : t === 'date' ? '定时' : t}
                  </MenuItem>
                ))}
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

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stack,
  Chip,
  Button,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Paper,
  IconButton,
  CircularProgress,
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Add as AddIcon,
  Pause as PauseIcon,
  PlayCircle as ResumeIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { TaskConfig, ScheduleInfo, ScheduleSummary, ConfigSchedulesResponse, ScheduleOperationResponse } from '../../types/task';

interface TaskSchedulePanelProps {
  configs: TaskConfig[];
}

const TaskSchedulePanel: React.FC<TaskSchedulePanelProps> = ({ configs }) => {
  const { fetchData, postData, deleteData, getApiState } = useApiStore();
  const [schedules, setSchedules] = useState<ScheduleInfo[]>([]);
  const [summary, setSummary] = useState<ScheduleSummary | null>(null);
  const [expanded, setExpanded] = useState<number | false>(false);
  const [configSchedules, setConfigSchedules] = useState<Record<number, string[]>>({});
  
  const schedulesUrl = '/v1/tasks/schedules';
  const summaryUrl = '/v1/tasks/schedules/summary';
  const { loading } = getApiState(schedulesUrl);

  const loadSchedules = useCallback(async () => {
    try {
      const [schedulesData, summaryData] = await Promise.all([
        fetchData<{ schedules: ScheduleInfo[] }>(schedulesUrl),
        fetchData<ScheduleSummary>(summaryUrl),
      ]);
      setSchedules(schedulesData.schedules || []);
      setSummary(summaryData);
    } catch (error) {
      console.error('Failed to load schedules:', error);
    }
  }, [fetchData, schedulesUrl, summaryUrl]);

  useEffect(() => {
    loadSchedules();
  }, [loadSchedules]);

  // derive per-config state lazily when expanded

  // Also eagerly load per-config schedule indices so counts are accurate without expanding
  useEffect(() => {
    const fetchAllConfigIndices = async () => {
      if (!configs || configs.length === 0) return;
      try {
        const results = await Promise.all(
          configs.map((cfg) =>
            fetchData<ConfigSchedulesResponse>(`/v1/tasks/configs/${cfg.id}/schedules`).catch(() => ({ config_id: cfg.id, schedule_ids: [] }))
          )
        );
        const map: Record<number, string[]> = {};
        results.forEach((r) => {
          map[r.config_id] = r.schedule_ids || [];
        });
        setConfigSchedules(map);
      } catch {
        // ignore; counts will be zero until expanded/explicit refresh
      }
    };
    fetchAllConfigIndices();
  }, [configs, fetchData]);

  const handleExpand = async (configId: number) => {
    setExpanded((prev) => (prev === configId ? false : configId));
    // Lazy-load schedule IDs for this config
    if (!configSchedules[configId]) {
      try {
        const resp = await fetchData<ConfigSchedulesResponse>(`/v1/tasks/configs/${configId}/schedules`);
        setConfigSchedules((prev) => ({ ...prev, [configId]: resp.schedule_ids || [] }));
      } catch {
        // ignore
      }
    }
  };

  const refreshForConfig = async (configId: number) => {
    // refresh both global and this config's index
    await loadSchedules();
    try {
      const resp = await fetchData<ConfigSchedulesResponse>(`/v1/tasks/configs/${configId}/schedules`);
      setConfigSchedules((prev) => ({ ...prev, [configId]: resp.schedule_ids || [] }));
    } catch {
      // ignore
    }
  };

  const handleCreateInstance = async (configId: number) => {
    try {
      const resp = await postData<ScheduleOperationResponse>(`/v1/tasks/configs/${configId}/schedules`, {});
      if (resp && resp.success) {
        await refreshForConfig(configId);
      }
    } catch (e) {
      console.error('Failed to create schedule instance:', e);
    }
  };

  const handlePause = async (scheduleId: string, configId: number) => {
    try {
      const resp = await postData<ScheduleOperationResponse>(`/v1/tasks/schedules/${scheduleId}/pause`, {});
      if (resp && resp.success) {
        await refreshForConfig(configId);
      }
    } catch (e) {
      console.error('Failed to pause schedule:', e);
    }
  };

  const handleResume = async (scheduleId: string, configId: number) => {
    try {
      const resp = await postData<ScheduleOperationResponse>(`/v1/tasks/schedules/${scheduleId}/resume`, {});
      if (resp && resp.success) {
        await refreshForConfig(configId);
      }
    } catch (e) {
      console.error('Failed to resume schedule:', e);
    }
  };

  const handleUnregister = async (scheduleId: string, configId: number) => {
    try {
      const resp = await deleteData<ScheduleOperationResponse>(`/v1/tasks/schedules/${scheduleId}`);
      if (resp && resp.success) {
        await refreshForConfig(configId);
      }
    } catch (e) {
      console.error('Failed to unregister schedule:', e);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {summary && (
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>调度摘要</Typography>
            <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              <Box>
                <Typography variant="body2" color="text.secondary">总实例数</Typography>
                <Typography variant="h4">{summary.total_schedules}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">活跃实例</Typography>
                <Typography variant="h4" color="success.main">{summary.active_schedules}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">暂停实例</Typography>
                <Typography variant="h4" color="warning.main">{summary.paused_schedules}</Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">错误实例</Typography>
                <Typography variant="h4" color="error.main">{summary.error_schedules}</Typography>
              </Box>
            </Box>
          </CardContent>
        </Card>
      )}

      {/* Expandable config → schedules list */}
      <Stack spacing={2}>
        {configs.map((cfg) => {
          const active = schedules.filter((s) => s.config_id === cfg.id);
          const allIds = configSchedules[cfg.id] || [];
          const activeIds = new Set(active.map((s) => s.schedule_id));
          const pausedIds = allIds.filter((id) => !activeIds.has(id));

          return (
            <Accordion key={cfg.id} expanded={expanded === cfg.id} onChange={() => handleExpand(cfg.id)}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', justifyContent: 'space-between' }}>
                  <Box>
                    <Typography variant="subtitle1">{cfg.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {cfg.task_type} · {cfg.scheduler_type}
                    </Typography>
                  </Box>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Chip size="small" label={`实例: ${allIds.length}`} />
                    <Button size="small" variant="outlined" startIcon={<AddIcon />} onClick={(e) => { e.stopPropagation(); handleCreateInstance(cfg.id); }}>
                      新增实例
                    </Button>
                  </Stack>
                </Box>
              </AccordionSummary>
              <AccordionDetails>
                {/* Active instances table */}
                <Typography variant="subtitle2" gutterBottom>活跃实例</Typography>
                <Table size="small" component={Paper}>
                  <TableHead>
                    <TableRow>
                      <TableCell>schedule_id</TableCell>
                      <TableCell>触发器</TableCell>
                      <TableCell>下次运行</TableCell>
                      <TableCell align="right">操作</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {active.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={4} align="center">无活跃实例</TableCell>
                      </TableRow>
                    ) : active.map((s) => (
                      <TableRow key={s.schedule_id}>
                        <TableCell sx={{ fontFamily: 'monospace' }}>{s.schedule_id}</TableCell>
                        <TableCell sx={{ fontFamily: 'monospace' }}>{s.schedule}</TableCell>
                        <TableCell>{s.next_run ? new Date(s.next_run).toLocaleString('zh-CN') : '-'}</TableCell>
                        <TableCell align="right">
                          <IconButton size="small" color="warning" onClick={() => handlePause(s.schedule_id, cfg.id)} title="暂停">
                            <PauseIcon fontSize="small" />
                          </IconButton>
                          <IconButton size="small" color="error" onClick={() => handleUnregister(s.schedule_id, cfg.id)} title="注销">
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                {/* Paused/Inactive instances */}
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>暂停/未激活实例</Typography>
                  {pausedIds.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">无</Typography>
                  ) : (
                    <Stack spacing={1}>
                      {pausedIds.map((sid) => (
                        <Box key={sid} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <Typography sx={{ fontFamily: 'monospace' }}>{sid}</Typography>
                          <Box>
                            <IconButton size="small" color="success" onClick={() => handleResume(sid, cfg.id)} title="恢复">
                              <ResumeIcon fontSize="small" />
                            </IconButton>
                            <IconButton size="small" color="error" onClick={() => handleUnregister(sid, cfg.id)} title="注销">
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Box>
                        </Box>
                      ))}
                    </Stack>
                  )}
                </Box>
              </AccordionDetails>
            </Accordion>
          );
        })}
      </Stack>
    </Box>
  );
};

export default TaskSchedulePanel;

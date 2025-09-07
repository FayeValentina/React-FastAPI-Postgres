import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Alert,
  Tabs,
  Tab,
  Paper,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  Dashboard as DashboardIcon,
} from '@mui/icons-material';
import { useApiStore } from '../stores/api-store';
import { useAuthStore } from '../stores/auth-store';
import ManagementLayout from '../components/Layout/ManagementLayout';
import TaskConfigList from '../components/Tasks/TaskConfigList';
import TaskConfigDialog from '../components/Tasks/TaskConfigDialog';
import TaskSchedulePanel from '../components/Tasks/TaskSchedulePanel';
import TaskExecutionPanel from '../components/Tasks/TaskExecutionPanel';
import { TaskConfig, TaskConfigCreate, TaskConfigUpdate, ScheduleInfo, ConfigSchedulesResponse } from '../types/task';

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
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

const TaskManagementPage: React.FC = () => {
  const { fetchData, postData, patchData, deleteData, getApiState } = useApiStore();
  const { user } = useAuthStore();
  
  const [tabValue, setTabValue] = useState(0);
  const [configs, setConfigs] = useState<TaskConfig[]>([]);
  const [scheduleCounts, setScheduleCounts] = useState<Record<number, { active: number; paused: number }>>({});
  const [selectedConfig, setSelectedConfig] = useState<TaskConfig | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const configsUrl = '/v1/tasks/configs';
  const { loading, error } = getApiState(configsUrl);

  const isSuperuser = user?.is_superuser || false;

  const loadConfigs = useCallback(async () => {
    if (!isSuperuser) return;
    
    try {
      const response = await fetchData<{ items: TaskConfig[], total: number }>(configsUrl);
      const items = response.items || [];
      setConfigs(items);

      // also compute schedule counts per config (active vs paused/inactive)
      try {
        const all = await fetchData<{ schedules: ScheduleInfo[] }>(`/v1/tasks/schedules`);
        const activeByConfig = new Map<number, number>();
        (all.schedules || []).forEach((s) => {
          if (s.config_id != null) {
            activeByConfig.set(s.config_id, (activeByConfig.get(s.config_id) || 0) + 1);
          }
        });

        const idsResp = await Promise.all(
          items.map((cfg) =>
            fetchData<ConfigSchedulesResponse>(`/v1/tasks/configs/${cfg.id}/schedules`).catch(() => ({ config_id: cfg.id, schedule_ids: [] }))
          )
        );

        const counts: Record<number, { active: number; paused: number }> = {};
        idsResp.forEach((resp) => {
          const cfgId = resp.config_id;
          const total = (resp.schedule_ids || []).length;
          const active = activeByConfig.get(cfgId) || 0;
          const paused = Math.max(total - active, 0);
          counts[cfgId] = { active, paused };
        });
        setScheduleCounts(counts);
      } catch {
        // if schedule endpoints fail, fall back to zeros
        const empty: Record<number, { active: number; paused: number }> = {};
        items.forEach((cfg) => (empty[cfg.id] = { active: 0, paused: 0 }));
        setScheduleCounts(empty);
      }
    } catch (error) {
      console.error('Failed to load configs:', error);
    }
  }, [fetchData, configsUrl, isSuperuser]);

  useEffect(() => {
    loadConfigs();
  }, [loadConfigs]);

  const handleCreateConfig = () => {
    setSelectedConfig(null);
    setDialogOpen(true);
  };

  const handleEditConfig = (config: TaskConfig) => {
    setSelectedConfig(config);
    setDialogOpen(true);
  };

  const handleDeleteConfig = async (config: TaskConfig) => {
    if (window.confirm(`确定要删除任务配置 "${config.name}" 吗？`)) {
      try {
        await deleteData(`/v1/tasks/configs/${config.id}`);
        await loadConfigs();
      } catch (error) {
        console.error('Failed to delete config:', error);
      }
    }
  };

  const handleSaveConfig = async (data: TaskConfigCreate | TaskConfigUpdate) => {
    try {
      if (selectedConfig) {
        await patchData(`/v1/tasks/configs/${selectedConfig.id}`, data);
      } else {
        await postData('/v1/tasks/configs', data);
      }
      setDialogOpen(false);
      await loadConfigs();
    } catch (error) {
      console.error('Failed to save config:', error);
    }
  };

  // config 与调度已分离，调度操作移至调度面板

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
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3, gap: 2, flexWrap: 'wrap' }}>
          <Typography variant="h4" gutterBottom sx={{ fontSize: { xs: 20, sm: 24, md: 28 } }}>
            任务管理中心
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
            <Button
              variant="outlined"
              startIcon={<DashboardIcon />}
              onClick={() => window.location.href = '/management/monitoring'}
            >
              系统监控
            </Button>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={loadConfigs}
              disabled={loading}
            >
              刷新
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleCreateConfig}
              disabled={loading}
            >
              创建任务
            </Button>
          </Box>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error.message || '加载失败，请稍后重试'}
          </Alert>
        )}

        <Paper sx={{ mb: 3 }}>
          <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)}>
            <Tab label="任务配置" />
            <Tab label="调度管理" />
            <Tab label="执行记录" />
          </Tabs>
        </Paper>

        <TabPanel value={tabValue} index={0}>
          <TaskConfigList
            configs={configs}
            loading={loading}
            onEdit={handleEditConfig}
            onDelete={handleDeleteConfig}
            scheduleCounts={scheduleCounts}
          />
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          <TaskSchedulePanel configs={configs} />
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          <TaskExecutionPanel configs={configs} />
        </TabPanel>

        <TaskConfigDialog
          open={dialogOpen}
          config={selectedConfig}
          onClose={() => setDialogOpen(false)}
          onSave={handleSaveConfig}
        />
      </Box>
    </ManagementLayout>
  );
};

export default TaskManagementPage;

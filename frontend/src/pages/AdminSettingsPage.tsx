import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Snackbar,
  Stack,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import RestoreIcon from '@mui/icons-material/Restore';

import ManagementLayout from '../components/Layout/ManagementLayout';
import { useAuthStore } from '../stores/auth-store';
import { useApiStore } from '../stores/api-store';
import {
  SettingsTable,
  SettingsEditDialog,
  SettingsFeatureToggles,
  ADMIN_SETTING_DEFINITION_MAP,
  type AdminSettingDefinition,
} from '../components/AdminSettings';
import {
  AdminSettingKey,
  AdminSettingValue,
  AdminSettingsResponse,
} from '../types/adminSettings';

const SETTINGS_URL = '/v1/admin/settings';
const RESET_URL = '/v1/admin/settings/reset';

type SnackbarState = {
  open: boolean;
  message: string;
  severity: 'success' | 'error';
};

const initialSnackbar: SnackbarState = {
  open: false,
  message: '',
  severity: 'success',
};

const coerceValueForDefinition = (
  definition: AdminSettingDefinition | null,
  value: AdminSettingValue | undefined,
): number | boolean | null => {
  if (!definition) {
    return null;
  }

  if (value === undefined || value === null) {
    return null;
  }

  switch (definition.type) {
    case 'boolean':
      if (typeof value === 'boolean') {
        return value;
      }
      if (typeof value === 'number') {
        return value !== 0;
      }
      if (typeof value === 'string') {
        return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
      }
      return Boolean(value);
    case 'int':
    case 'float': {
      const num = typeof value === 'number' ? value : Number(value);
      if (Number.isNaN(num)) {
        return null;
      }
      if (definition.type === 'int') {
        return Math.trunc(num);
      }
      return num;
    }
    default:
      return null;
  }
};

const AdminSettingsPage: React.FC = () => {
  const { user } = useAuthStore();
  const { fetchData, putData, postData, getApiState, setError, setData } = useApiStore();

  const [selectedKey, setSelectedKey] = useState<AdminSettingKey | null>(null);
  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState<SnackbarState>(initialSnackbar);

  const apiState = getApiState(SETTINGS_URL) as {
    data: AdminSettingsResponse | null;
    loading: boolean;
    error: Error | null;
  };

  const { data: settings, loading, error } = apiState;

  const loadSettings = useCallback(async () => {
    try {
      await fetchData<AdminSettingsResponse>(SETTINGS_URL);
    } catch (err) {
      const message = err instanceof Error ? err.message : '加载失败，请稍后重试';
      setSnackbar({ open: true, message, severity: 'error' });
    }
  }, [fetchData]);

  useEffect(() => {
    if (user?.is_superuser) {
      void loadSettings();
    }
  }, [user?.is_superuser, loadSettings]);

  const selectedDefinition = useMemo(() => {
    if (!selectedKey) {
      return null;
    }
    return ADMIN_SETTING_DEFINITION_MAP[selectedKey];
  }, [selectedKey]);

  const currentValue = useMemo(() => {
    if (!selectedKey || !settings) {
      return null;
    }
    const definition = ADMIN_SETTING_DEFINITION_MAP[selectedKey] ?? null;
    const value = settings.effective?.[selectedKey];
    return coerceValueForDefinition(definition, value);
  }, [selectedKey, settings]);

  const defaultValue = useMemo(() => {
    if (!selectedKey || !settings) {
      return null;
    }
    const definition = ADMIN_SETTING_DEFINITION_MAP[selectedKey] ?? null;
    const value = settings.defaults?.[selectedKey];
    return coerceValueForDefinition(definition, value);
  }, [selectedKey, settings]);

  const handleEdit = (key: AdminSettingKey) => {
    setSelectedKey(key);
    setError(SETTINGS_URL, null);
  };

  const handleCloseDialog = () => {
    if (saving) {
      return;
    }
    setSelectedKey(null);
  };

  const applyUpdate = async (key: AdminSettingKey, value: number | boolean) => {
    setSaving(true);
    try {
      const response = await putData<AdminSettingsResponse>(SETTINGS_URL, { [key]: value });
      setSnackbar({ open: true, message: '设置已更新', severity: 'success' });
      setSelectedKey(null);
      return response;
    } catch (err) {
      const message = err instanceof Error ? err.message : '更新失败，请稍后重试';
      setSnackbar({ open: true, message, severity: 'error' });
      throw err;
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async (value: number | boolean) => {
    if (!selectedKey) {
      return;
    }
    await applyUpdate(selectedKey, value);
  };

  const resetSettings = useCallback(
    async (keys?: AdminSettingKey[], successMessage?: string) => {
      setSaving(true);
      try {
        const payload = keys && keys.length > 0 ? { keys } : {};
        const response = await postData<AdminSettingsResponse>(RESET_URL, payload);
        setData<AdminSettingsResponse>(SETTINGS_URL, response);
        setSnackbar({
          open: true,
          message: successMessage ?? '设置已恢复默认值',
          severity: 'success',
        });
        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : '重置失败，请稍后重试';
        setSnackbar({ open: true, message, severity: 'error' });
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [postData, setData],
  );

  const handleResetToDefault = useCallback(async () => {
    if (!selectedKey) {
      return;
    }
    try {
      await resetSettings([selectedKey], '设置已重置为默认值');
      setSelectedKey(null);
    } catch {
      // 错误提示已在 resetSettings 中处理
    }
  }, [resetSettings, selectedKey]);

  const handleResetAll = useCallback(async () => {
    const confirmed = window.confirm('确认将所有设置恢复为默认值？该操作会覆盖当前所有自定义配置。');
    if (!confirmed) {
      return;
    }
    try {
      await resetSettings(undefined, '所有设置已恢复默认值');
    } catch {
      // 错误提示已在 resetSettings 中处理
    }
  }, [resetSettings]);

  const handleToggleUpdate = async (key: AdminSettingKey, value: boolean) => {
    await applyUpdate(key, value);
  };

  const handleCloseSnackbar = () => {
    setSnackbar(initialSnackbar);
  };

  if (!user?.is_superuser) {
    return (
      <ManagementLayout>
        <Alert severity="error" sx={{ mt: 4 }}>
          您没有权限访问系统设置。需要超级管理员权限。
        </Alert>
      </ManagementLayout>
    );
  }

  return (
    <ManagementLayout>
      <Stack spacing={3}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2}>
          <Box>
            <Typography variant="h4" sx={{ fontSize: { xs: 20, sm: 24, md: 28 } }}>
              系统设置管理
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              管理动态检索参数，实时调优 RAG 服务表现。
            </Typography>
          </Box>
          <Stack direction="row" spacing={1}>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={() => void loadSettings()}
              disabled={loading || saving}
            >
              刷新
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<RestoreIcon />}
              onClick={() => void handleResetAll()}
              disabled={loading || saving}
            >
              重置全部
            </Button>
          </Stack>
        </Stack>

        {loading && !settings && (
          <Stack alignItems="center" sx={{ my: 6 }}>
            <CircularProgress />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
              正在加载当前配置…
            </Typography>
          </Stack>
        )}

        {error && (
          <Alert severity="error">
            {error.message || '加载失败，请稍后重试'}
          </Alert>
        )}

        {settings && settings.redis_status === 'unavailable' && (
          <Alert severity="warning">
            无法连接 Redis，已回退到默认配置。请检查缓存服务状态。
          </Alert>
        )}

        {settings && settings.updated_at && (
          <Alert severity="info" icon={false}>
            上次更新时间：{new Date(settings.updated_at).toLocaleString()}
          </Alert>
        )}
        {settings && (
          <SettingsFeatureToggles
            settings={settings}
            loading={loading || saving}
            onToggle={handleToggleUpdate}
          />
        )}

        <SettingsTable
          settings={settings ?? null}
          loading={loading || saving}
          onEdit={handleEdit}
        />
      </Stack>

      <SettingsEditDialog
        open={Boolean(selectedKey && selectedDefinition)}
        definition={selectedDefinition}
        currentValue={currentValue}
        defaultValue={defaultValue}
        onClose={handleCloseDialog}
        onSubmit={handleSubmit}
        onResetToDefault={handleResetToDefault}
        saving={saving}
      />

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={snackbar.severity} sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </ManagementLayout>
  );
};

export default AdminSettingsPage;

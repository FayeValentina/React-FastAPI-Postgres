import React from 'react';
import {
  Paper,
  Stack,
  Typography,
  Tooltip,
  Switch,
  Chip,
  Divider,
  Box,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

import {
  ADMIN_SETTING_DEFINITION_MAP,
  FEATURE_TOGGLE_KEYS,
} from './settingDefinitions';
import {
  AdminSettingKey,
  AdminSettingValue,
  AdminSettingsResponse,
} from '../../types/adminSettings';

interface SettingsFeatureTogglesProps {
  settings: AdminSettingsResponse | null;
  loading: boolean;
  onToggle: (key: AdminSettingKey, value: boolean) => void | Promise<void>;
}

const coerceBoolean = (value: AdminSettingValue): boolean => {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === 'string') {
    return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
  }
  if (typeof value === 'number') {
    return value !== 0;
  }
  return Boolean(value);
};

const formatBoolean = (value: AdminSettingValue): string => {
  if (value === null || value === undefined) {
    return '—';
  }
  return coerceBoolean(value) ? '是' : '否';
};

const SettingsFeatureToggles: React.FC<SettingsFeatureTogglesProps> = ({
  settings,
  loading,
  onToggle,
}) => {
  if (!settings) {
    return null;
  }

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack spacing={2} divider={<Divider flexItem />}>
        {FEATURE_TOGGLE_KEYS.map((key) => {
          const definition = ADMIN_SETTING_DEFINITION_MAP[key];
          if (!definition) {
            return null;
          }

          const defaultValue = settings.defaults?.[key] ?? null;
          const effectiveValue = settings.effective?.[key] ?? null;
          const overrideValue = settings.overrides?.[key];
          const hasOverride = overrideValue !== undefined && overrideValue !== null;
          const checked =
            effectiveValue === null || effectiveValue === undefined
              ? coerceBoolean(defaultValue)
              : coerceBoolean(effectiveValue);

          return (
            <Stack
              key={key}
              direction={{ xs: 'column', sm: 'row' }}
              spacing={2}
              alignItems={{ xs: 'flex-start', sm: 'center' }}
              justifyContent="space-between"
            >
              <Stack spacing={0.5} sx={{ flex: 1, minWidth: 0 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="subtitle1" component="div">
                    {definition.label}
                  </Typography>
                  {definition.description && (
                    <Tooltip title={definition.description} placement="top" arrow>
                      <InfoOutlinedIcon fontSize="small" color="action" />
                    </Tooltip>
                  )}
                </Stack>
                {definition.description && (
                  <Typography variant="body2" color="text.secondary">
                    {definition.description}
                  </Typography>
                )}
                <Typography variant="caption" color="text.secondary">
                  {key}
                </Typography>
              </Stack>

              <Stack direction="column" spacing={0.5} alignItems={{ xs: 'flex-start', sm: 'flex-end' }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Switch
                    checked={checked}
                    disabled={loading}
                    onChange={(event) => {
                      const nextValue = event.target.checked;
                      void onToggle(key, nextValue);
                    }}
                    inputProps={{ 'aria-label': definition.label }}
                  />
                  {hasOverride && <Chip size="small" color="primary" label="已覆盖" />}
                </Stack>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    默认: {formatBoolean(defaultValue)} / 当前: {formatBoolean(effectiveValue)}
                  </Typography>
                </Box>
              </Stack>
            </Stack>
          );
        })}
      </Stack>
    </Paper>
  );
};

export default SettingsFeatureToggles;

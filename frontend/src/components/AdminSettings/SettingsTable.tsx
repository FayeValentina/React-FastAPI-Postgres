import React from 'react';
import {
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Chip,
  Tooltip,
  Stack,
  Typography,
  Box,
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import EditIcon from '@mui/icons-material/Edit';

import {
  ADMIN_SETTING_DEFINITIONS,
  FEATURE_TOGGLE_KEYS,
  AdminSettingDefinition,
} from './settingDefinitions';
import {
  AdminSettingKey,
  AdminSettingValue,
  AdminSettingsResponse,
} from '../../types/adminSettings';

interface SettingsTableProps {
  settings: AdminSettingsResponse | null;
  loading: boolean;
  onEdit: (key: AdminSettingKey) => void;
}

const formatValue = (value: AdminSettingValue): string => {
  if (value === null || value === undefined) {
    return '—';
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value.toString() : value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  return String(value);
};

const renderDescription = (definition: AdminSettingDefinition) => {
  if (!definition.description) {
    return null;
  }
  return (
    <Tooltip title={definition.description} placement="top" arrow>
      <InfoOutlinedIcon fontSize="small" color="action" />
    </Tooltip>
  );
};

const FEATURE_TOGGLE_KEY_SET = new Set<AdminSettingKey>(FEATURE_TOGGLE_KEYS);

const TABLE_SETTING_DEFINITIONS = ADMIN_SETTING_DEFINITIONS.filter(
  ({ key }) => !FEATURE_TOGGLE_KEY_SET.has(key),
);

const SettingsTable: React.FC<SettingsTableProps> = ({ settings, loading, onEdit }) => {
  return (
    <TableContainer component={Paper} sx={{ mt: 2 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ width: '30%' }}>设置项</TableCell>
            <TableCell sx={{ width: '20%' }}>默认值</TableCell>
            <TableCell sx={{ width: '20%' }}>当前生效值</TableCell>
            <TableCell sx={{ width: '20%' }}>覆盖值</TableCell>
            <TableCell align="right" sx={{ width: '10%' }}>操作</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {TABLE_SETTING_DEFINITIONS.map((definition) => {
            const { key } = definition;
            const defaultValue = settings?.defaults?.[key] ?? null;
            const effectiveValue = settings?.effective?.[key] ?? null;
            const overrideValue = settings?.overrides?.[key];
            const hasOverride = overrideValue !== undefined && overrideValue !== null;

            return (
              <TableRow key={key} hover>
                <TableCell>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Box>
                      <Typography variant="subtitle2" component="div">
                        {definition.label}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {key}
                      </Typography>
                    </Box>
                    {renderDescription(definition)}
                  </Stack>
                </TableCell>
                <TableCell>{formatValue(defaultValue)}</TableCell>
                <TableCell>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <span>{formatValue(effectiveValue)}</span>
                    {hasOverride && <Chip size="small" color="primary" label="已覆盖" />}
                  </Stack>
                </TableCell>
                <TableCell>
                  {hasOverride ? (
                    <Typography color="primary" component="span">
                      {formatValue(overrideValue ?? null)}
                    </Typography>
                  ) : (
                    <Typography color="text.secondary" component="span">
                      （无）
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
                  <Button
                    size="small"
                    variant="outlined"
                    startIcon={<EditIcon />}
                    onClick={() => onEdit(key)}
                    disabled={loading}
                  >
                    编辑
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default SettingsTable;

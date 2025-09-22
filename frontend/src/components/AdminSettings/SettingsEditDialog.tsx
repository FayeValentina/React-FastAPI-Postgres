import React, { useEffect, useMemo, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControlLabel,
  TextField,
  Stack,
  Typography,
  Alert,
  Switch,
} from '@mui/material';

import { AdminSettingDefinition } from './settingDefinitions';

interface SettingsEditDialogProps {
  open: boolean;
  definition: AdminSettingDefinition | null;
  currentValue: number | boolean | null;
  defaultValue: number | boolean | null;
  onClose: () => void;
  onSubmit: (value: number | boolean) => Promise<void> | void;
  onResetToDefault: (defaultValue: number | boolean) => Promise<void> | void;
  saving?: boolean;
}

const SettingsEditDialog: React.FC<SettingsEditDialogProps> = ({
  open,
  definition,
  currentValue,
  defaultValue,
  onClose,
  onSubmit,
  onResetToDefault,
  saving = false,
}) => {
  const [inputValue, setInputValue] = useState('');
  const [boolValue, setBoolValue] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && definition) {
      if (definition.type === 'boolean') {
        const resolved =
          typeof currentValue === 'boolean'
            ? currentValue
            : typeof defaultValue === 'boolean'
              ? defaultValue
              : false;
        setBoolValue(resolved);
        setInputValue('');
      } else {
        const initialValue =
          currentValue !== null && currentValue !== undefined
            ? currentValue
            : defaultValue !== null && defaultValue !== undefined
              ? defaultValue
              : '';
        setInputValue(initialValue === '' ? '' : String(initialValue));
      }
      setError(null);
    } else if (!open) {
      setInputValue('');
      setBoolValue(false);
      setError(null);
    }
  }, [open, definition, currentValue, defaultValue]);

  const helperRange = useMemo(() => {
    if (!definition || definition.type === 'boolean') return '';
    const parts: string[] = [];
    if (definition.min !== undefined) {
      parts.push(`≥ ${definition.min}`);
    }
    if (definition.max !== undefined) {
      parts.push(`≤ ${definition.max}`);
    }
    return parts.join('，');
  }, [definition]);

  const parseValue = (): number | boolean | null => {
    if (!definition) {
      return null;
    }

    if (definition.type === 'boolean') {
      setError(null);
      return boolValue;
    }

    if (inputValue === '') {
      setError('请输入数值');
      return null;
    }

    const parsed = definition.type === 'int' ? Number.parseInt(inputValue, 10) : Number.parseFloat(inputValue);

    if (Number.isNaN(parsed)) {
      setError('请输入有效的数字');
      return null;
    }

    if (!Number.isFinite(parsed)) {
      setError('数值超出范围');
      return null;
    }

    if (definition.type === 'int' && !Number.isInteger(parsed)) {
      setError('该设置需要整数值');
      return null;
    }

    if (definition.min !== undefined && parsed < definition.min) {
      setError(`值不能小于 ${definition.min}`);
      return null;
    }

    if (definition.max !== undefined && parsed > definition.max) {
      setError(`值不能大于 ${definition.max}`);
      return null;
    }

    setError(null);
    return parsed;
  };

  const handleSubmit = async () => {
    const parsed = parseValue();
    if (parsed === null || parsed === undefined) {
      return;
    }

    await onSubmit(parsed);
  };

  const formatDisplayValue = (value: number | boolean | null) => {
    if (value === null || value === undefined) {
      return '—';
    }
    if (typeof value === 'boolean') {
      return value ? '是' : '否';
    }
    if (Number.isInteger(value)) {
      return value.toString();
    }
    return value.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
  };

  const handleReset = async () => {
    if (defaultValue === null || defaultValue === undefined || definition === null) {
      return;
    }
    setError(null);
    await onResetToDefault(defaultValue);
  };

  if (!definition) {
    return null;
  }

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} fullWidth maxWidth="sm">
      <DialogTitle>调整设置：{definition.label}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ mt: 1 }}>
          {definition.description && (
            <Alert severity="info" icon={false}>
              <Typography variant="body2">{definition.description}</Typography>
            </Alert>
          )}
          <Typography variant="body2" color="text.secondary">
            当前生效值：{formatDisplayValue(currentValue)}，默认值：{formatDisplayValue(defaultValue)}
          </Typography>
          {definition.type === 'boolean' ? (
            <FormControlLabel
              control={
                <Switch
                  checked={boolValue}
                  onChange={(event) => setBoolValue(event.target.checked)}
                  disabled={saving}
                />
              }
              label={boolValue ? '启用' : '停用'}
            />
          ) : (
            <TextField
              label="新的覆盖值"
              type="number"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              fullWidth
              inputProps={{
                step: definition.step ?? (definition.type === 'float' ? 0.01 : 1),
                min: definition.min,
                max: definition.max,
              }}
              error={Boolean(error)}
              helperText={error ?? helperRange}
              disabled={saving}
            />
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving}>
          取消
        </Button>
        <Button onClick={handleReset} color="inherit" disabled={saving || defaultValue === null || defaultValue === undefined}>
          重置为默认值
        </Button>
        <Button onClick={handleSubmit} variant="contained" disabled={saving}>
          保存
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SettingsEditDialog;

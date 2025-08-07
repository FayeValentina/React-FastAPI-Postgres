import React, { useState } from 'react';
import {
  Box,
  IconButton,
  Tooltip,
  Menu,
  MenuItem,
  Typography,
  Switch,
  FormControlLabel,
  Divider,
  Chip,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Settings as SettingsIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Timer as TimerIcon,
} from '@mui/icons-material';

interface AutoRefreshControlProps {
  isRunning: boolean;
  interval: number;
  onToggle: () => void;
  onRefresh: () => void;
  onSetInterval: (interval: number) => void;
  disabled?: boolean;
}

const INTERVAL_OPTIONS = [
  { label: '10秒', value: 10000 },
  { label: '30秒', value: 30000 },
  { label: '1分钟', value: 60000 },
  { label: '5分钟', value: 300000 },
  { label: '10分钟', value: 600000 },
];

const AutoRefreshControl: React.FC<AutoRefreshControlProps> = ({
  isRunning,
  interval,
  onToggle,
  onRefresh,
  onSetInterval,
  disabled = false,
}) => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const menuOpen = Boolean(anchorEl);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleIntervalChange = (newInterval: number) => {
    onSetInterval(newInterval);
    handleMenuClose();
  };

  const formatInterval = (ms: number) => {
    if (ms < 60000) return `${ms / 1000}秒`;
    return `${ms / 60000}分钟`;
  };

  const getCurrentIntervalLabel = () => {
    const option = INTERVAL_OPTIONS.find(opt => opt.value === interval);
    return option ? option.label : formatInterval(interval);
  };

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      {/* 刷新状态指示器 */}
      <Chip
        icon={<TimerIcon />}
        label={isRunning ? `自动刷新 (${getCurrentIntervalLabel()})` : '已暂停'}
        color={isRunning ? 'success' : 'default'}
        size="small"
        variant="outlined"
      />

      {/* 手动刷新按钮 */}
      <Tooltip title="立即刷新">
        <IconButton
          onClick={onRefresh}
          disabled={disabled}
          size="small"
        >
          <RefreshIcon />
        </IconButton>
      </Tooltip>

      {/* 播放/暂停按钮 */}
      <Tooltip title={isRunning ? '暂停自动刷新' : '开始自动刷新'}>
        <IconButton
          onClick={onToggle}
          disabled={disabled}
          color={isRunning ? 'primary' : 'default'}
          size="small"
        >
          {isRunning ? <PauseIcon /> : <PlayIcon />}
        </IconButton>
      </Tooltip>

      {/* 设置按钮 */}
      <Tooltip title="刷新设置">
        <IconButton
          onClick={handleMenuOpen}
          disabled={disabled}
          size="small"
        >
          <SettingsIcon />
        </IconButton>
      </Tooltip>

      {/* 设置菜单 */}
      <Menu
        anchorEl={anchorEl}
        open={menuOpen}
        onClose={handleMenuClose}
        PaperProps={{
          sx: { minWidth: 200 }
        }}
      >
        <Box sx={{ px: 2, py: 1 }}>
          <Typography variant="subtitle2" color="text.secondary">
            自动刷新设置
          </Typography>
        </Box>
        
        <MenuItem>
          <FormControlLabel
            control={
              <Switch
                checked={isRunning}
                onChange={onToggle}
                size="small"
              />
            }
            label="启用自动刷新"
            sx={{ width: '100%' }}
          />
        </MenuItem>
        
        <Divider />
        
        <Box sx={{ px: 2, py: 1 }}>
          <Typography variant="caption" color="text.secondary">
            刷新间隔
          </Typography>
        </Box>
        
        {INTERVAL_OPTIONS.map((option) => (
          <MenuItem
            key={option.value}
            selected={interval === option.value}
            onClick={() => handleIntervalChange(option.value)}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
              <Typography>{option.label}</Typography>
              {interval === option.value && (
                <Chip label="当前" size="small" color="primary" />
              )}
            </Box>
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
};

export default AutoRefreshControl;
import React from 'react';
import {
  Card,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Grid,
  Chip,
  Box,
} from '@mui/material';
import {
  FilterList as FilterIcon,
  Autorenew as AutorenewIcon,
} from '@mui/icons-material';
import { SessionFilters, SessionStatus, SessionType } from '../../types/session';

interface SessionFilterBarProps {
  filters: SessionFilters;
  onFiltersChange: (filters: SessionFilters) => void;
  autoRefresh: boolean;
  onAutoRefreshChange: (enabled: boolean) => void;
}

const SessionFilterBar: React.FC<SessionFilterBarProps> = ({
  filters,
  onFiltersChange,
  autoRefresh,
  onAutoRefreshChange,
}) => {
  const handleStatusChange = (status: SessionStatus | '') => {
    onFiltersChange({
      ...filters,
      status: status || undefined,
    });
  };

  const handleTypeChange = (type: SessionType | '') => {
    onFiltersChange({
      ...filters,
      session_type: type || undefined,
    });
  };

  const clearFilters = () => {
    onFiltersChange({});
  };

  const hasActiveFilters = filters.status || filters.session_type;

  return (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Grid container spacing={2} alignItems="center">
          <Grid item>
            <FilterIcon color="action" />
          </Grid>
          
          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>状态</InputLabel>
              <Select
                value={filters.status || ''}
                onChange={(e) => handleStatusChange(e.target.value as SessionStatus | '')}
                label="状态"
              >
                <MenuItem value="">全部</MenuItem>
                <MenuItem value="pending">等待中</MenuItem>
                <MenuItem value="running">运行中</MenuItem>
                <MenuItem value="completed">已完成</MenuItem>
                <MenuItem value="failed">失败</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6} md={2}>
            <FormControl fullWidth size="small">
              <InputLabel>类型</InputLabel>
              <Select
                value={filters.session_type || ''}
                onChange={(e) => handleTypeChange(e.target.value as SessionType | '')}
                label="类型"
              >
                <MenuItem value="">全部</MenuItem>
                <MenuItem value="manual">手动</MenuItem>
                <MenuItem value="auto">自动</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={autoRefresh}
                  onChange={(e) => onAutoRefreshChange(e.target.checked)}
                  icon={<AutorenewIcon />}
                  checkedIcon={<AutorenewIcon />}
                />
              }
              label="自动刷新"
            />
          </Grid>

          <Grid item xs={12} md={3}>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {hasActiveFilters && (
                <Chip
                  label="清除过滤"
                  onClick={clearFilters}
                  onDelete={clearFilters}
                  size="small"
                  variant="outlined"
                />
              )}
              {filters.status && (
                <Chip
                  label={`状态: ${filters.status}`}
                  size="small"
                  color="primary"
                />
              )}
              {filters.session_type && (
                <Chip
                  label={`类型: ${filters.session_type}`}
                  size="small"
                  color="secondary"
                />
              )}
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

export default SessionFilterBar;
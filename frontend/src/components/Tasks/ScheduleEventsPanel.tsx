import React, { useEffect, useState, useCallback } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  CircularProgress,
  Alert,
  Box,
  Chip,
  IconButton,
  Tooltip,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Pagination,
} from '@mui/material';
import {
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
  TimelineOppositeContent,
} from '@mui/lab';
import {
  Event as EventIcon,
  Refresh as RefreshIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  Warning as WarningIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  FilterList as FilterIcon,
  ViewTimeline as TimelineIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { ScheduleEvent } from '../../types/task';

interface ScheduleEventsPanelProps {
  refreshTrigger?: number;
}

const ScheduleEventsPanel: React.FC<ScheduleEventsPanelProps> = ({ refreshTrigger = 0 }) => {
  const { fetchData, getApiState } = useApiStore();
  
  const [events, setEvents] = useState<ScheduleEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<ScheduleEvent | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'table' | 'timeline'>('table');
  
  // 分页状态
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const pageSize = 20;
  
  // 筛选状态
  const [filters, setFilters] = useState({
    job_id: '',
    event_type: '',
    search: '',
  });

  const buildEventsUrl = () => {
    const params = new URLSearchParams();
    params.append('limit', pageSize.toString());
    params.append('offset', ((page - 1) * pageSize).toString());
    
    if (filters.job_id) params.append('job_id', filters.job_id);
    if (filters.event_type) params.append('event_type', filters.event_type);
    
    return `/v1/tasks/events?${params.toString()}`;
  };

  const eventsUrl = buildEventsUrl();
  const { loading, error } = getApiState(eventsUrl);

  const loadEvents = useCallback(async () => {
    try {
      const data = await fetchData<{ events: ScheduleEvent[], total: number }>(eventsUrl);
      if (data) {
        setEvents(data.events || []);
        setTotalPages(Math.ceil((data.total || 0) / pageSize));
      }
    } catch (error) {
      console.error('Failed to load schedule events:', error);
    }
  }, [fetchData, eventsUrl]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents, refreshTrigger, page, filters]);

  const handleViewEventDetails = (event: ScheduleEvent) => {
    setSelectedEvent(event);
    setDetailDialogOpen(true);
  };

  const handlePageChange = (_event: React.ChangeEvent<unknown>, newPage: number) => {
    setPage(newPage);
  };

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1); // 重置到第一页
  };

  const clearFilters = () => {
    setFilters({ job_id: '', event_type: '', search: '' });
    setPage(1);
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('zh-CN');
  };

  const getEventTypeIcon = (eventType: string) => {
    switch (eventType.toLowerCase()) {
      case 'job_executed':
        return <SuccessIcon color="success" />;
      case 'job_error':
        return <ErrorIcon color="error" />;
      case 'job_missed':
        return <WarningIcon color="warning" />;
      case 'job_added':
        return <AddIcon color="info" />;
      case 'job_removed':
        return <RemoveIcon color="default" />;
      default:
        return <InfoIcon color="default" />;
    }
  };

  const getEventTypeColor = (eventType: string): 'success' | 'error' | 'warning' | 'info' | 'default' => {
    switch (eventType.toLowerCase()) {
      case 'job_executed': return 'success';
      case 'job_error': return 'error';
      case 'job_missed': return 'warning';
      case 'job_added': return 'info';
      case 'job_removed': return 'default';
      default: return 'default';
    }
  };

  const getEventTypeName = (eventType: string) => {
    const typeMap: Record<string, string> = {
      'job_executed': '任务执行',
      'job_error': '执行错误',
      'job_missed': '错过执行',
      'job_added': '任务添加',
      'job_removed': '任务移除',
      'job_modified': '任务修改',
      'scheduler_started': '调度器启动',
      'scheduler_shutdown': '调度器关闭',
    };
    return typeMap[eventType] || eventType;
  };

  const renderEventDetailsDialog = () => (
    <Dialog
      open={detailDialogOpen}
      onClose={() => setDetailDialogOpen(false)}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle>
        事件详情 - {selectedEvent?.job_name}
      </DialogTitle>
      <DialogContent>
        {selectedEvent && (
          <Box>
            <Typography variant="subtitle2" gutterBottom>基本信息</Typography>
            <Table size="small" sx={{ mb: 2 }}>
              <TableBody>
                <TableRow>
                  <TableCell component="th" scope="row">事件ID</TableCell>
                  <TableCell>{selectedEvent.id}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell component="th" scope="row">任务ID</TableCell>
                  <TableCell>{selectedEvent.job_id}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell component="th" scope="row">任务名称</TableCell>
                  <TableCell>{selectedEvent.job_name}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell component="th" scope="row">事件类型</TableCell>
                  <TableCell>
                    <Chip
                      icon={getEventTypeIcon(selectedEvent.event_type)}
                      label={getEventTypeName(selectedEvent.event_type)}
                      color={getEventTypeColor(selectedEvent.event_type)}
                      size="small"
                    />
                  </TableCell>
                </TableRow>
                <TableRow>
                  <TableCell component="th" scope="row">发生时间</TableCell>
                  <TableCell>{formatDateTime(selectedEvent.created_at)}</TableCell>
                </TableRow>
              </TableBody>
            </Table>

            {selectedEvent.result && Object.keys(selectedEvent.result).length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>执行结果</Typography>
                <Box component="pre" sx={{ 
                  bgcolor: 'grey.100', 
                  p: 1, 
                  borderRadius: 1, 
                  fontSize: '0.75rem',
                  overflow: 'auto',
                  maxHeight: '200px'
                }}>
                  {JSON.stringify(selectedEvent.result, null, 2)}
                </Box>
              </Box>
            )}

            {selectedEvent.error_message && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom color="error">错误信息</Typography>
                <Alert severity="error">
                  {selectedEvent.error_message}
                </Alert>
              </Box>
            )}

            {selectedEvent.error_traceback && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom color="error">错误堆栈</Typography>
                <Box component="pre" sx={{ 
                  bgcolor: 'error.light', 
                  color: 'error.contrastText',
                  p: 1, 
                  borderRadius: 1, 
                  fontSize: '0.75rem',
                  overflow: 'auto',
                  maxHeight: '300px'
                }}>
                  {selectedEvent.error_traceback}
                </Box>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setDetailDialogOpen(false)}>关闭</Button>
      </DialogActions>
    </Dialog>
  );

  const renderFilters = () => (
    <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
      <TextField
        label="任务ID"
        variant="outlined"
        size="small"
        value={filters.job_id}
        onChange={(e) => handleFilterChange('job_id', e.target.value)}
        sx={{ minWidth: 150 }}
      />
      <FormControl size="small" sx={{ minWidth: 150 }}>
        <InputLabel>事件类型</InputLabel>
        <Select
          value={filters.event_type}
          label="事件类型"
          onChange={(e) => handleFilterChange('event_type', e.target.value)}
        >
          <MenuItem value="">全部</MenuItem>
          <MenuItem value="job_executed">任务执行</MenuItem>
          <MenuItem value="job_error">执行错误</MenuItem>
          <MenuItem value="job_missed">错过执行</MenuItem>
          <MenuItem value="job_added">任务添加</MenuItem>
          <MenuItem value="job_removed">任务移除</MenuItem>
        </Select>
      </FormControl>
      <Button
        variant="outlined"
        size="small"
        onClick={clearFilters}
        disabled={!filters.job_id && !filters.event_type}
      >
        清除筛选
      </Button>
    </Box>
  );

  const renderTableView = () => (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>事件类型</TableCell>
            <TableCell>任务名称</TableCell>
            <TableCell>发生时间</TableCell>
            <TableCell>状态</TableCell>
            <TableCell align="right">操作</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {events.map((event) => (
            <TableRow key={event.id}>
              <TableCell>
                <Chip
                  icon={getEventTypeIcon(event.event_type)}
                  label={getEventTypeName(event.event_type)}
                  color={getEventTypeColor(event.event_type)}
                  size="small"
                />
              </TableCell>
              <TableCell>
                <Typography variant="body2">
                  {event.job_name}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  ID: {event.job_id}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="caption">
                  {formatDateTime(event.created_at)}
                </Typography>
              </TableCell>
              <TableCell>
                {event.error_message ? (
                  <Chip label="异常" color="error" size="small" />
                ) : (
                  <Chip label="正常" color="success" size="small" />
                )}
              </TableCell>
              <TableCell align="right">
                <Tooltip title="查看详情">
                  <IconButton 
                    size="small"
                    onClick={() => handleViewEventDetails(event)}
                  >
                    <InfoIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

  const renderTimelineView = () => (
    <Timeline>
      {events.map((event, index) => (
        <TimelineItem key={event.id}>
          <TimelineOppositeContent sx={{ m: 'auto 0' }} align="right" variant="caption" color="text.secondary">
            {formatDateTime(event.created_at)}
          </TimelineOppositeContent>
          <TimelineSeparator>
            <TimelineDot color={getEventTypeColor(event.event_type)}>
              {getEventTypeIcon(event.event_type)}
            </TimelineDot>
            {index < events.length - 1 && <TimelineConnector />}
          </TimelineSeparator>
          <TimelineContent sx={{ py: '12px', px: 2 }}>
            <Box onClick={() => handleViewEventDetails(event)} sx={{ cursor: 'pointer' }}>
              <Typography variant="h6" component="span">
                {getEventTypeName(event.event_type)}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {event.job_name}
              </Typography>
              {event.error_message && (
                <Alert severity="error" sx={{ mt: 1 }}>
                  {event.error_message.substring(0, 100)}...
                </Alert>
              )}
            </Box>
          </TimelineContent>
        </TimelineItem>
      ))}
    </Timeline>
  );

  return (
    <>
      <Card>
        <CardHeader
          avatar={<EventIcon color="primary" />}
          title="调度事件"
          subheader={`最近的调度事件记录`}
          action={
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Tooltip title={viewMode === 'table' ? '切换到时间线视图' : '切换到表格视图'}>
                <IconButton 
                  onClick={() => setViewMode(viewMode === 'table' ? 'timeline' : 'table')}
                >
                  {viewMode === 'table' ? <TimelineIcon /> : <FilterIcon />}
                </IconButton>
              </Tooltip>
              <IconButton onClick={loadEvents} disabled={loading}>
                <RefreshIcon />
              </IconButton>
            </Box>
          }
        />
        <CardContent>
          {renderFilters()}
          
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
              <CircularProgress />
            </Box>
          ) : error ? (
            <Alert severity="error">
              加载调度事件失败
            </Alert>
          ) : events.length === 0 ? (
            <Alert severity="info">
              暂无调度事件记录
            </Alert>
          ) : (
            <Box>
              {viewMode === 'table' ? renderTableView() : renderTimelineView()}
              
              {totalPages > 1 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                  <Pagination
                    count={totalPages}
                    page={page}
                    onChange={handlePageChange}
                    color="primary"
                  />
                </Box>
              )}
            </Box>
          )}
        </CardContent>
      </Card>

      {renderEventDetailsDialog()}
    </>
  );
};

export default ScheduleEventsPanel;
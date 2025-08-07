import React, { useEffect, useState, useCallback } from 'react';
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  Alert,
  IconButton,
  Grid,
  Paper,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  Analytics as AnalyticsIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingUpIcon,
  Schedule as ScheduleIcon,
  Speed as SpeedIcon,
  Queue as QueueIcon,
  Lightbulb as RecommendationIcon,
  ExpandMore as ExpandMoreIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
  Timeline as TimelineIcon,
  Assessment as AssessmentIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import { SystemAnalysis } from '../../types/task';

interface SystemAnalysisPanelProps {
  refreshTrigger?: number;
}

const SystemAnalysisPanel: React.FC<SystemAnalysisPanelProps> = ({ refreshTrigger = 0 }) => {
  const { fetchData, getApiState } = useApiStore();
  
  const [analysis, setAnalysis] = useState<SystemAnalysis | null>(null);
  const [expandedPanel, setExpandedPanel] = useState<string | false>('schedule');

  const analysisUrl = '/v1/tasks/analysis';
  const { loading, error } = getApiState(analysisUrl);

  const loadAnalysis = useCallback(async () => {
    try {
      const data = await fetchData<SystemAnalysis>(analysisUrl);
      setAnalysis(data);
    } catch (error) {
      console.error('Failed to load system analysis:', error);
    }
  }, [fetchData, analysisUrl]);

  useEffect(() => {
    loadAnalysis();
  }, [loadAnalysis, refreshTrigger]);

  const handleAccordionChange = (panel: string) => (_event: React.SyntheticEvent, isExpanded: boolean) => {
    setExpandedPanel(isExpanded ? panel : false);
  };

  const getOptimizationLevel = (optimizationNeeded: boolean, score?: number) => {
    if (score !== undefined) {
      if (score >= 90) return { level: '优秀', color: 'success' as const, icon: <CheckCircleIcon /> };
      if (score >= 70) return { level: '良好', color: 'info' as const, icon: <InfoIcon /> };
      if (score >= 50) return { level: '一般', color: 'warning' as const, icon: <WarningIcon /> };
      return { level: '需要优化', color: 'error' as const, icon: <WarningIcon /> };
    }
    
    return optimizationNeeded 
      ? { level: '需要优化', color: 'warning' as const, icon: <WarningIcon /> }
      : { level: '正常', color: 'success' as const, icon: <CheckCircleIcon /> };
  };

  const renderScheduleAnalysis = () => {
    if (!analysis?.schedule_distribution) return null;

    const { schedule_distribution } = analysis;
    const optimization = getOptimizationLevel(schedule_distribution.optimization_needed);

    return (
      <Accordion 
        expanded={expandedPanel === 'schedule'} 
        onChange={handleAccordionChange('schedule')}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ScheduleIcon color="primary" />
            <Typography variant="h6">调度分析</Typography>
            <Chip 
              icon={optimization.icon}
              label={optimization.level} 
              color={optimization.color} 
              size="small" 
            />
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={3}>
            {/* 基础统计 */}
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  <AssessmentIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                  基础统计
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="primary">
                        {schedule_distribution.total_bot_schedules}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        总调度数
                      </Typography>
                    </Box>
                  </Grid>
                  <Grid item xs={6}>
                    <Box sx={{ textAlign: 'center' }}>
                      <Typography variant="h4" color="warning.main">
                        {schedule_distribution.max_tasks_per_hour}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        峰值任务/小时
                      </Typography>
                    </Box>
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* 高峰时段分析 */}
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  <TimelineIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                  高峰时段
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                  {schedule_distribution.peak_hours.map(hour => (
                    <Chip 
                      key={hour} 
                      label={`${hour.toString().padStart(2, '0')}:00`} 
                      color="primary"
                      size="small" 
                    />
                  ))}
                </Box>
                <Typography variant="body2" color="text.secondary">
                  这些时段的任务密度最高，可能需要负载均衡优化
                </Typography>
              </Paper>
            </Grid>

            {/* 时间分布 */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  <TrendingUpIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                  24小时分布
                </Typography>
                <Box sx={{ mb: 2 }}>
                  {Object.entries(schedule_distribution.time_distribution).map(([hour, count]) => {
                    const percentage = schedule_distribution.total_bot_schedules > 0 
                      ? (count / schedule_distribution.total_bot_schedules * 100) 
                      : 0;
                    return (
                      <Box key={hour} sx={{ mb: 1 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                          <Typography variant="body2">
                            {hour.padStart(2, '0')}:00
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {count} 个任务 ({percentage.toFixed(1)}%)
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={percentage}
                          sx={{ height: 6, borderRadius: 3 }}
                        />
                      </Box>
                    );
                  })}
                </Box>
              </Paper>
            </Grid>

            {/* 优化建议 */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2 }}>
                <Typography variant="subtitle1" gutterBottom>
                  <RecommendationIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
                  优化建议
                </Typography>
                {schedule_distribution.recommendations.length > 0 ? (
                  <List dense>
                    {schedule_distribution.recommendations.map((recommendation, index) => (
                      <ListItem key={index}>
                        <ListItemIcon>
                          <RecommendationIcon color="primary" />
                        </ListItemIcon>
                        <ListItemText 
                          primary={recommendation}
                          primaryTypographyProps={{ variant: 'body2' }}
                        />
                      </ListItem>
                    ))}
                  </List>
                ) : (
                  <Alert severity="success">
                    当前调度配置优良，暂无优化建议
                  </Alert>
                )}
              </Paper>
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderConfigStats = () => {
    if (!analysis?.config_stats || Object.keys(analysis.config_stats).length === 0) return null;

    return (
      <Accordion 
        expanded={expandedPanel === 'config'} 
        onChange={handleAccordionChange('config')}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SpeedIcon color="primary" />
            <Typography variant="h6">配置统计</Typography>
            <Chip label={`${Object.keys(analysis.config_stats).length} 项`} size="small" />
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>配置项</TableCell>
                  <TableCell align="right">值</TableCell>
                  <TableCell>描述</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {Object.entries(analysis.config_stats).map(([key, value]) => (
                  <TableRow key={key}>
                    <TableCell component="th" scope="row">
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {key}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Chip 
                        label={typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" color="text.secondary">
                        {getConfigDescription(key)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </AccordionDetails>
      </Accordion>
    );
  };

  const renderQueueStatus = () => {
    if (!analysis?.queue_status || Object.keys(analysis.queue_status).length === 0) return null;

    return (
      <Accordion 
        expanded={expandedPanel === 'queue'} 
        onChange={handleAccordionChange('queue')}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <QueueIcon color="primary" />
            <Typography variant="h6">队列状态</Typography>
            <Chip label="实时监控" color="success" size="small" />
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={2}>
            {Object.entries(analysis.queue_status).map(([queueName, status]) => (
              <Grid item xs={12} sm={6} md={4} key={queueName}>
                <Paper sx={{ p: 2, textAlign: 'center' }}>
                  <QueueIcon sx={{ fontSize: 32, color: 'primary.main', mb: 1 }} />
                  <Typography variant="h6" gutterBottom>
                    {queueName}
                  </Typography>
                  <Box component="pre" sx={{ 
                    fontSize: '0.75rem', 
                    fontFamily: 'monospace',
                    bgcolor: 'grey.100',
                    p: 1,
                    borderRadius: 1,
                    textAlign: 'left',
                    overflow: 'auto'
                  }}>
                    {JSON.stringify(status, null, 2)}
                  </Box>
                </Paper>
              </Grid>
            ))}
          </Grid>
        </AccordionDetails>
      </Accordion>
    );
  };

  const getConfigDescription = (key: string): string => {
    const descriptions: Record<string, string> = {
      'max_workers': '最大工作进程数',
      'task_timeout': '任务超时时间',
      'retry_count': '重试次数',
      'queue_size': '队列大小',
      'memory_limit': '内存限制',
      'cpu_limit': 'CPU限制',
      'scheduler_interval': '调度间隔',
      'cleanup_interval': '清理间隔',
    };
    return descriptions[key] || '配置项';
  };

  const renderContent = () => {
    if (loading) {
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      );
    }

    if (error) {
      return (
        <Alert severity="error">
          加载系统分析失败
        </Alert>
      );
    }

    if (!analysis) {
      return (
        <Alert severity="info">
          暂无系统分析数据
        </Alert>
      );
    }

    return (
      <Box>
        {renderScheduleAnalysis()}
        {renderConfigStats()}
        {renderQueueStatus()}
        
        {/* 如果没有任何数据 */}
        {!analysis.schedule_distribution && !analysis.config_stats && !analysis.queue_status && (
          <Alert severity="info">
            系统分析数据为空，请检查后端配置
          </Alert>
        )}
      </Box>
    );
  };

  return (
    <Card>
      <CardHeader
        avatar={<AnalyticsIcon color="primary" />}
        title="系统分析"
        subheader="深度分析系统性能和配置"
        action={
          <IconButton onClick={loadAnalysis} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        }
      />
      <CardContent>
        {renderContent()}
      </CardContent>
    </Card>
  );
};

export default SystemAnalysisPanel;
import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Grid,
  Chip,
  Box,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
  Settings as SettingsIcon,
  Error as ErrorIcon,
  Assessment as StatsIcon,
} from '@mui/icons-material';
import { ScrapeSessionResponse } from '../../types/session';

interface SessionDetailDialogProps {
  open: boolean;
  session: ScrapeSessionResponse | null;
  onClose: () => void;
}

const SessionDetailDialog: React.FC<SessionDetailDialogProps> = ({
  open,
  session,
  onClose,
}) => {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));

  if (!session) {
    return null;
  }

  const formatDateTime = (dateString: string | null) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString('zh-CN');
  };

  const formatDuration = (seconds: number | null) => {
    if (!seconds) return '-';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${hours}h ${minutes}m ${secs}s`;
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      fullScreen={fullScreen}
      scroll="paper"
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6">
            会话详情 #{session.id}
          </Typography>
          <Chip
            label={session.status}
            color={session.status === 'completed' ? 'success' : session.status === 'failed' ? 'error' : 'primary'}
            size="small"
          />
        </Box>
        <Button onClick={onClose} startIcon={<CloseIcon />}>
          关闭
        </Button>
      </DialogTitle>

      <DialogContent dividers>
        {/* Basic Information */}
        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <StatsIcon />
          基本信息
        </Typography>
        
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">会话ID</Typography>
            <Typography variant="body1">{session.id}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">Bot配置ID</Typography>
            <Typography variant="body1">{session.bot_config_id}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">会话类型</Typography>
            <Typography variant="body1">{session.session_type}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">状态</Typography>
            <Typography variant="body1">{session.status}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">开始时间</Typography>
            <Typography variant="body1">{formatDateTime(session.started_at)}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">结束时间</Typography>
            <Typography variant="body1">{formatDateTime(session.completed_at)}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">持续时间</Typography>
            <Typography variant="body1">{formatDuration(session.duration_seconds)}</Typography>
          </Grid>
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">创建时间</Typography>
            <Typography variant="body1">{formatDateTime(session.created_at)}</Typography>
          </Grid>
        </Grid>

        <Divider sx={{ mb: 3 }} />

        {/* Results Statistics */}
        <Typography variant="h6" gutterBottom>
          爬取结果
        </Typography>
        
        <Grid container spacing={2} sx={{ mb: 3 }}>
          <Grid item xs={6} sm={3}>
            <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'primary.light', borderRadius: 1 }}>
              <Typography variant="h4" color="primary.contrastText">
                {session.total_posts_found}
              </Typography>
              <Typography variant="caption" color="primary.contrastText">
                总帖子数
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'secondary.light', borderRadius: 1 }}>
              <Typography variant="h4" color="secondary.contrastText">
                {session.total_comments_found}
              </Typography>
              <Typography variant="caption" color="secondary.contrastText">
                总评论数
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'success.light', borderRadius: 1 }}>
              <Typography variant="h4" color="success.contrastText">
                {session.quality_comments_count}
              </Typography>
              <Typography variant="caption" color="success.contrastText">
                质量评论
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Box sx={{ textAlign: 'center', p: 2, bgcolor: 'info.light', borderRadius: 1 }}>
              <Typography variant="h4" color="info.contrastText">
                {session.published_count}
              </Typography>
              <Typography variant="caption" color="info.contrastText">
                已发布
              </Typography>
            </Box>
          </Grid>
        </Grid>

        {/* Configuration Snapshot */}
        {session.config_snapshot && (
          <Accordion sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <SettingsIcon />
                <Typography variant="h6">配置快照</Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <pre style={{ fontSize: '12px', overflow: 'auto' }}>
                {JSON.stringify(session.config_snapshot, null, 2)}
              </pre>
            </AccordionDetails>
          </Accordion>
        )}

        {/* Error Details */}
        {session.error_message && (
          <Accordion sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ErrorIcon color="error" />
                <Typography variant="h6" color="error">错误详情</Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body2" color="error" paragraph>
                <strong>错误消息:</strong> {session.error_message}
              </Typography>
              {session.error_details && (
                <pre style={{ fontSize: '12px', overflow: 'auto', color: theme.palette.error.main }}>
                  {JSON.stringify(session.error_details, null, 2)}
                </pre>
              )}
            </AccordionDetails>
          </Accordion>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} variant="contained">
          关闭
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SessionDetailDialog;
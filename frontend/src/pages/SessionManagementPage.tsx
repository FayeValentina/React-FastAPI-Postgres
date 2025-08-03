import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Grid,
  Alert,
  CircularProgress,
  Fab,
} from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';
import { useApiStore } from '../stores/api-store';
import ManagementLayout from '../components/Layout/ManagementLayout';
import SessionStatsPanel from '../components/Scraper/SessionStatsPanel';
import SessionFilterBar from '../components/Scraper/SessionFilterBar';
import SessionCard from '../components/Scraper/SessionCard';
import SessionDetailDialog from '../components/Scraper/SessionDetailDialog';
import { ScrapeSessionResponse, SessionFilters } from '../types/session';

const SessionManagementPage: React.FC = () => {
  
  const { fetchData, getApiState } = useApiStore();
  
  const [sessions, setSessions] = useState<ScrapeSessionResponse[]>([]);
  const [selectedSession, setSelectedSession] = useState<ScrapeSessionResponse | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [filters, setFilters] = useState<SessionFilters>({});
  const [autoRefresh, setAutoRefresh] = useState(true);

  // API states
  const sessionsApiUrl = '/v1/scraping/scrape-sessions';
  const { loading: sessionsLoading, error: sessionsError } = getApiState(sessionsApiUrl);

  const loadSessions = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filters.status) params.append('status', filters.status);
      if (filters.session_type) params.append('session_type', filters.session_type);
      
      const url = `${sessionsApiUrl}${params.toString() ? `?${params.toString()}` : ''}`;
      const data = await fetchData<ScrapeSessionResponse[]>(url);
      setSessions(data || []);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  }, [fetchData, filters, sessionsApiUrl]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Auto refresh for running sessions
  useEffect(() => {
    if (!autoRefresh) return;
    
    // 检查是否有运行中的会话
    const hasRunningSessions = sessions.some(s => s.status === 'running');
    if (!hasRunningSessions) return;
    
    const interval = setInterval(() => {
      loadSessions();
    }, 5000);

    return () => clearInterval(interval);
  }, [autoRefresh, sessions, loadSessions]);

  // Check if there are running sessions
  

  const handleSessionClick = (session: ScrapeSessionResponse) => {
    setSelectedSession(session);
    setDetailDialogOpen(true);
  };

  const handleFilterChange = (newFilters: SessionFilters) => {
    setFilters(newFilters);
  };


  return (
    <ManagementLayout>
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" gutterBottom>
            会话管理
          </Typography>
          <Fab
            color="primary"
            aria-label="refresh"
            onClick={loadSessions}
            disabled={sessionsLoading}
            size="small"
          >
            <RefreshIcon />
          </Fab>
        </Box>

        {/* Statistics Panel */}
        <SessionStatsPanel />

        {/* Filter Bar */}
        <SessionFilterBar 
          filters={filters}
          onFiltersChange={handleFilterChange}
          autoRefresh={autoRefresh}
          onAutoRefreshChange={setAutoRefresh}
        />

        {sessionsError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {sessionsError.message || '加载失败，请稍后重试'}
          </Alert>
        )}

        {/* Sessions Grid */}
        {sessionsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress />
          </Box>
        ) : sessions.length === 0 ? (
          <Box sx={{ textAlign: 'center', mt: 4 }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              还没有爬取会话
            </Typography>
            <Typography variant="body2" color="text.secondary">
              创建Bot配置并执行爬取后，会话记录会显示在这里
            </Typography>
          </Box>
        ) : (
          <Grid container spacing={3}>
            {sessions.map((session) => (
              <Grid item xs={12} sm={6} lg={4} key={session.id}>
                <SessionCard
                  session={session}
                  onClick={() => handleSessionClick(session)}
                />
              </Grid>
            ))}
          </Grid>
        )}

        {/* Session Detail Dialog */}
        <SessionDetailDialog
          open={detailDialogOpen}
          session={selectedSession}
          onClose={() => setDetailDialogOpen(false)}
        />
      </Box>
    </ManagementLayout>
  );
};

export default SessionManagementPage;
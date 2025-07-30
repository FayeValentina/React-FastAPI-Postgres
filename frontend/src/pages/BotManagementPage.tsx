import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Grid,
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Fab,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/auth-store';
import { useApiStore } from '../stores/api-store';
import ScraperLayout from '../components/Scraper/ScraperLayout';
import BotConfigCard from '../components/Scraper/BotConfigCard';
import BotConfigDialog from '../components/Scraper/BotConfigDialog';
import { BotConfigResponse } from '../types/bot';

const BotManagementPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const { fetchData, postData, deleteData, getApiState } = useApiStore();
  
  const [configs, setConfigs] = useState<BotConfigResponse[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<BotConfigResponse | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [configToDelete, setConfigToDelete] = useState<BotConfigResponse | null>(null);

  // API states
  const listApiUrl = '/v1/bot-configs';
  const { loading: listLoading, error: listError } = getApiState(listApiUrl);

  const loadConfigs = useCallback(async () => {
    try {
      const data = await fetchData<BotConfigResponse[]>(listApiUrl);
      setConfigs(data || []);
    } catch (error) {
      console.error('Failed to load bot configs:', error);
    }
  }, [fetchData, listApiUrl]);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    loadConfigs();
  }, [isAuthenticated, navigate, loadConfigs]);

  const handleCreateConfig = () => {
    setSelectedConfig(null);
    setDialogOpen(true);
  };

  const handleEditConfig = (config: BotConfigResponse) => {
    setSelectedConfig(config);
    setDialogOpen(true);
  };

  const handleDeleteConfig = (config: BotConfigResponse) => {
    setConfigToDelete(config);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!configToDelete) return;

    try {
      await deleteData(`/v1/bot-configs/${configToDelete.id}`);
      await loadConfigs(); // Reload the list
      setDeleteDialogOpen(false);
      setConfigToDelete(null);
    } catch (error) {
      console.error('Failed to delete config:', error);
    }
  };

  const handleToggleConfig = async (config: BotConfigResponse) => {
    try {
      await postData(`/v1/bot-configs/${config.id}/toggle`, {});
      await loadConfigs(); // Reload the list
    } catch (error) {
      console.error('Failed to toggle config:', error);
    }
  };

  const handleDialogSubmit = async () => {
    setDialogOpen(false);
    await loadConfigs(); // Reload the list
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <ScraperLayout>
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" gutterBottom>
            Bot配置管理
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={loadConfigs}
              disabled={listLoading}
            >
              刷新
            </Button>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleCreateConfig}
              disabled={listLoading}
            >
              创建新配置
            </Button>
          </Box>
        </Box>

        {listError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {listError.message || '加载失败，请稍后重试'}
          </Alert>
        )}

        {listLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
            <CircularProgress />
          </Box>
        ) : configs.length === 0 ? (
          <Box sx={{ textAlign: 'center', mt: 4 }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              还没有任何Bot配置
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              创建你的第一个爬虫Bot配置来开始使用
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleCreateConfig}
            >
              创建第一个配置
            </Button>
          </Box>
        ) : (
          <Grid container spacing={3}>
            {configs.map((config) => (
              <Grid item xs={12} sm={6} lg={4} key={config.id}>
                <BotConfigCard
                  config={config}
                  onEdit={handleEditConfig}
                  onDelete={handleDeleteConfig}
                  onToggle={handleToggleConfig}
                  loading={listLoading}
                />
              </Grid>
            ))}
          </Grid>
        )}

        {/* Floating Action Button for mobile */}
        <Fab
          color="primary"
          aria-label="add"
          onClick={handleCreateConfig}
          sx={{
            position: 'fixed',
            bottom: 16,
            right: 16,
            display: { xs: 'flex', sm: 'none' },
          }}
        >
          <AddIcon />
        </Fab>

        {/* Create/Edit Dialog */}
        <BotConfigDialog
          open={dialogOpen}
          config={selectedConfig}
          onClose={() => setDialogOpen(false)}
          onSubmit={handleDialogSubmit}
        />

        {/* Delete Confirmation Dialog */}
        <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
          <DialogTitle>确认删除</DialogTitle>
          <DialogContent>
            <Typography>
              确定要删除配置 "{configToDelete?.name}" 吗？此操作无法撤销。
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteDialogOpen(false)}>取消</Button>
            <Button onClick={confirmDelete} color="error" variant="contained">
              删除
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </ScraperLayout>
  );
};

export default BotManagementPage;
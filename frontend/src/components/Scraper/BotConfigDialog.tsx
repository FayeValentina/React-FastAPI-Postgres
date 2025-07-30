import React, { useState, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  CircularProgress,
  IconButton,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import {
  Close as CloseIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import { useApiStore } from '../../stores/api-store';
import BotConfigForm from './BotConfigForm';
import { BotConfigCreate, BotConfigResponse, BotConfigUpdate } from '../../types/bot';

interface BotConfigDialogProps {
  open: boolean;
  config?: BotConfigResponse | null;
  onClose: () => void;
  onSubmit: () => void;
}

const BotConfigDialog: React.FC<BotConfigDialogProps> = ({
  open,
  config,
  onClose,
  onSubmit,
}) => {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));
  const { postData, patchData } = useApiStore();
  
  const [submitLoading, setSubmitLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const formSubmitRef = useRef<(() => void) | null>(null);

  const isEdit = !!config;
  const title = isEdit ? `编辑配置: ${config.name}` : '创建新的Bot配置';

  const handleFormSubmit = async (formData: BotConfigCreate | BotConfigUpdate) => {
    setSubmitLoading(true);
    setSubmitError(null);

    try {
      if (isEdit && config) {
        // Update existing config
        await patchData(`/v1/bot-configs/${config.id}`, formData);
      } else {
        // Create new config
        await postData('/v1/bot-configs', formData);
      }
      
      // Success - close dialog and notify parent
      onSubmit();
      onClose();
    } catch (error: unknown) {
      console.error('Form submission failed:', error);
      const errorMessage = error instanceof Error ? error.message : '操作失败，请稍后重试';
      setSubmitError(errorMessage);
    } finally {
      setSubmitLoading(false);
    }
  };

  const handleSave = () => {
    if (formSubmitRef.current) {
      formSubmitRef.current();
    }
  };

  const handleClose = () => {
    if (!submitLoading) {
      setSubmitError(null);
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      fullScreen={fullScreen}
      scroll="paper"
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {title}
        <IconButton
          aria-label="close"
          onClick={handleClose}
          disabled={submitLoading}
          sx={{ color: 'text.secondary' }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent dividers>
        <BotConfigForm
          config={config}
          onSubmit={handleFormSubmit}
          loading={submitLoading}
          error={submitError}
          formSubmitRef={formSubmitRef}
        />
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button
          onClick={handleClose}
          disabled={submitLoading}
          variant="outlined"
        >
          取消
        </Button>
        <Button
          onClick={handleSave}
          disabled={submitLoading}
          variant="contained"
          startIcon={submitLoading ? <CircularProgress size={20} /> : <SaveIcon />}
        >
          {submitLoading ? '保存中...' : isEdit ? '更新配置' : '创建配置'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default BotConfigDialog;
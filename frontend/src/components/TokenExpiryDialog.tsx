import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
} from '@mui/material';
import { Warning as WarningIcon } from '@mui/icons-material';

interface TokenExpiryDialogProps {
  open: boolean;
  onConfirm: () => void;
}

export const TokenExpiryDialog: React.FC<TokenExpiryDialogProps> = ({
  open,
  onConfirm,
}) => {
  return (
    <Dialog
      open={open}
      disableEscapeKeyDown
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <WarningIcon color="warning" />
          <Typography variant="h6">登录已过期</Typography>
        </Box>
      </DialogTitle>
      
      <DialogContent>
        <Typography variant="body1">
          您的登录会话已过期，请重新登录以继续使用系统。
        </Typography>
      </DialogContent>
      
      <DialogActions>
        <Button
          onClick={onConfirm}
          variant="contained"
          color="primary"
          fullWidth
        >
          重新登录
        </Button>
      </DialogActions>
    </Dialog>
  );
};
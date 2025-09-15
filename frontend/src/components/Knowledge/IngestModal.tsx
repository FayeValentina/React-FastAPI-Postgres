import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Switch,
  TextField,
  Typography,
} from '@mui/material';

interface IngestModalProps {
  open: boolean;
  onClose: () => void;
  onIngest: (content: string, overwrite: boolean) => Promise<void> | void;
  documentTitle?: string | null;
}

const IngestModal: React.FC<IngestModalProps> = ({ open, onClose, onIngest, documentTitle }) => {
  const [content, setContent] = useState('');
  const [overwrite, setOverwrite] = useState(false);

  useEffect(() => {
    if (!open) {
      setContent('');
      setOverwrite(false);
    }
  }, [open]);

  const handleSubmit = async () => {
    if (!content.trim()) return;
    await onIngest(content, overwrite);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>注入文档内容{documentTitle ? `：${documentTitle}` : ''}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          支持普通文本或 Markdown，系统会自动清理并切分。
        </Typography>
        <Box>
          <TextField
            multiline
            minRows={8}
            fullWidth
            placeholder="在此粘贴文本或Markdown内容..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
        </Box>
        <Box sx={{ mt: 1 }}>
          <FormControlLabel
            control={<Switch checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} />}
            label="覆盖已有分块（将清空原有内容）"
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>取消</Button>
        <Button variant="contained" onClick={handleSubmit}>开始注入</Button>
      </DialogActions>
    </Dialog>
  );
};

export default IngestModal;


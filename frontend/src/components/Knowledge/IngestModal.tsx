import React, { ChangeEvent, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';

interface IngestModalProps {
  open: boolean;
  onClose: () => void;
  onIngest: (params: { content: string; file: File | null; overwrite: boolean }) => Promise<void> | void;
  documentTitle?: string | null;
}

const IngestModal: React.FC<IngestModalProps> = ({ open, onClose, onIngest, documentTitle }) => {
  const [content, setContent] = useState('');
  const [overwrite, setOverwrite] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  const acceptList = useMemo(
    () => '.txt,.md,.markdown,.csv,.tsv,.json,.yaml,.yml',
    []
  );

  const allowedMime = useMemo(
    () => [
      'text/plain',
      'text/markdown',
      'text/x-markdown',
      'text/csv',
      'text/tab-separated-values',
      'application/json',
      'text/xml',
      'application/xml',
      'application/yaml',
      'application/x-yaml',
    ],
    []
  );

  useEffect(() => {
    if (!open) {
      setContent('');
      setOverwrite(false);
      setFile(null);
      setFileError(null);
    }
  }, [open]);

  const validateFile = (selected: File) => {
    const extension = selected.name?.split('.').pop()?.toLowerCase() ?? '';
    const hasAllowedExt = extension ? acceptList.split(',').some((ext) => ext.replace('.', '') === extension) : false;
    const hasAllowedMime = allowedMime.includes(selected.type) || selected.type.startsWith('text/');
    if (!hasAllowedExt && !hasAllowedMime) {
      return '仅支持上传文本文件（如 .txt/.md/.csv 等）';
    }
    return null;
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files?.[0] ?? null;
    if (!selected) {
      setFile(null);
      setFileError(null);
      return;
    }
    const validationMessage = validateFile(selected);
    if (validationMessage) {
      setFile(null);
      setFileError(validationMessage);
      return;
    }
    setFileError(null);
    setFile(selected);
    setContent('');
  };

  const handleRemoveFile = () => {
    setFile(null);
    setFileError(null);
  };

  const handleSubmit = async () => {
    if (!file && !content.trim()) return;
    await onIngest({
      content: file ? '' : content,
      file,
      overwrite,
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>注入文档内容{documentTitle ? `：${documentTitle}` : ''}</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          支持粘贴文本、Markdown 内容或上传文本类文件（如 .txt/.md/.csv）。
        </Typography>
        <Stack spacing={2}>
          <Box>
            <Button variant="outlined" component="label">
              {file ? '重新选择文件' : '上传文本文件'}
              <input
                hidden
                type="file"
                accept={acceptList}
                onChange={handleFileChange}
              />
            </Button>
            {file && (
              <Box sx={{ mt: 1 }}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="body2" color="text.secondary">
                    已选择：{file.name}
                  </Typography>
                  <Button size="small" onClick={handleRemoveFile}>
                    移除
                  </Button>
                </Stack>
              </Box>
            )}
            {fileError && (
              <Typography variant="caption" color="error" sx={{ display: 'block', mt: 0.5 }}>
                {fileError}
              </Typography>
            )}
          </Box>
          <TextField
            multiline
            minRows={8}
            fullWidth
            placeholder="在此粘贴文本或Markdown内容..."
            value={content}
            onChange={(e) => setContent(e.target.value)}
            disabled={Boolean(file)}
          />
        </Stack>
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

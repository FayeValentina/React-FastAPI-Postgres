import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  TextField,
} from '@mui/material';
import { KnowledgeDocumentCreate } from '../../types';

interface CreateDocumentModalProps {
  open: boolean;
  onClose: () => void;
  onCreate: (payload: KnowledgeDocumentCreate) => Promise<void> | void;
}

const CreateDocumentModal: React.FC<CreateDocumentModalProps> = ({ open, onClose, onCreate }) => {
  const [form, setForm] = useState<KnowledgeDocumentCreate>({
    title: '',
    source_type: '',
    source_ref: '',
    language: '',
  });

  useEffect(() => {
    if (!open) {
      setForm({ title: '', source_type: '', source_ref: '', language: '' });
    }
  }, [open]);

  const handleChange = (key: keyof KnowledgeDocumentCreate) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
  };

  const handleSubmit = async () => {
    const payload: KnowledgeDocumentCreate = {
      // Only include fields if truthy to avoid sending empty strings
      ...(form.title ? { title: form.title } : {}),
      ...(form.source_type ? { source_type: form.source_type } : {}),
      ...(form.source_ref ? { source_ref: form.source_ref } : {}),
      ...(form.language ? { language: form.language } : {}),
    };
    await onCreate(payload);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>创建新文档</DialogTitle>
      <DialogContent>
        <Box component="form" sx={{ mt: 1 }}>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="标题"
                value={form.title || ''}
                onChange={handleChange('title')}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="来源类型"
                placeholder="upload/url/crawl/api"
                value={form.source_type || ''}
                onChange={handleChange('source_type')}
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="语言"
                placeholder="zh/en/ja"
                value={form.language || ''}
                onChange={handleChange('language')}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="来源标识"
                placeholder="URL/路径/外部ID/批次ID"
                value={form.source_ref || ''}
                onChange={handleChange('source_ref')}
              />
            </Grid>
          </Grid>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>取消</Button>
        <Button variant="contained" onClick={handleSubmit}>创建</Button>
      </DialogActions>
    </Dialog>
  );
};

export default CreateDocumentModal;


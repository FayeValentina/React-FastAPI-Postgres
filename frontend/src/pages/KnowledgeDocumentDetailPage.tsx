import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Save as SaveIcon,
} from '@mui/icons-material';
import ManagementLayout from '../components/Layout/ManagementLayout';
import api from '../services/api';
import { useNotifications } from '../components/Common/NotificationSystem';
import { extractErrorMessage, type ApiError } from '../utils/errorHandler';
import { KnowledgeChunkRead, KnowledgeDocumentRead } from '../types';

const KnowledgeDocumentDetailPage: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { success, error } = useNotifications();

  const docId = useMemo(() => Number(id), [id]);
  const [loading, setLoading] = useState(false);
  const [document, setDocument] = useState<KnowledgeDocumentRead | null>(null);
  const [chunks, setChunks] = useState<KnowledgeChunkRead[]>([]);

  // editable state
  const [title, setTitle] = useState('');
  const [tagsText, setTagsText] = useState('');
  const [metaText, setMetaText] = useState('');

  const loadData = useCallback(async () => {
    if (!docId) return;
    setLoading(true);
    try {
      const [doc, cks] = await Promise.all([
        api.get<KnowledgeDocumentRead>(`/v1/knowledge/documents/${docId}`),
        api.get<KnowledgeChunkRead[]>(`/v1/knowledge/documents/${docId}/chunks`),
      ]);

      setDocument(doc);
      setChunks(cks);

      // init edit fields
      setTitle(doc?.title || '');
      setTagsText((doc?.tags || []).join(', '));
      setMetaText(
        doc?.meta ? JSON.stringify(doc.meta, null, 2) : ''
      );
    } catch (e) {
      error(extractErrorMessage(e as ApiError) || '加载文档详情失败');
    } finally {
      setLoading(false);
    }
  }, [docId, error]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSave = async () => {
    if (!document) return;
    // parse tags
    const tags = tagsText
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    // parse meta JSON
    let meta: unknown = undefined;
    if (metaText.trim().length > 0) {
      try {
        meta = JSON.parse(metaText);
      } catch {
        error('Metadata 不是合法的 JSON');
        return;
      }
    } else {
      meta = null; // allow clearing
    }

    try {
      await api.patch<KnowledgeDocumentRead>(`/v1/knowledge/documents/${document.id}`, {
        // Only include changed fields
        ...(title !== (document.title || '') ? { title } : {}),
        ...(JSON.stringify(tags) !== JSON.stringify(document.tags || []) ? { tags } : {}),
        ...(JSON.stringify(meta) !== JSON.stringify(document.meta ?? null) ? { meta } : {}),
      });
      success('更新成功');
      await loadData();
    } catch (e) {
      error(extractErrorMessage(e as ApiError) || '更新失败');
    }
  };

  const metaPlaceholder = '{\n  "key": "value"\n}';

  return (
    <ManagementLayout>
      <Box>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/management/knowledge')}>返回</Button>
            <Typography variant="h5">文档详情</Typography>
          </Stack>
          <Stack direction="row" spacing={1}>
            <Button variant="contained" startIcon={<SaveIcon />} onClick={handleSave} disabled={loading || !document}>保存</Button>
          </Stack>
        </Stack>

        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>元数据编辑</Typography>
                <Stack spacing={2}>
                  <TextField
                    label="标题"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    fullWidth
                  />
                  <TextField
                    label="标签（以逗号分隔）"
                    placeholder="tag1, tag2, tag3"
                    value={tagsText}
                    onChange={(e) => setTagsText(e.target.value)}
                    fullWidth
                  />
                  <TextField
                    label="Metadata (JSON)"
                    placeholder={metaPlaceholder}
                    value={metaText}
                    onChange={(e) => setMetaText(e.target.value)}
                    fullWidth
                    multiline
                    minRows={8}
                  />
                </Stack>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={7}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>文本分块预览</Typography>
                <Stack spacing={1}>
                  {chunks.map((ck) => (
                    <Box key={ck.id} sx={{ p: 1.5, borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
                      <Stack direction="row" spacing={1} sx={{ mb: 0.5 }} alignItems="center">
                        <Chip size="small" label={`#${ck.chunk_index ?? '-'}`} />
                        <Typography variant="caption" color="text.secondary">
                          {new Date(ck.created_at).toLocaleString()}
                        </Typography>
                      </Stack>
                      <Typography sx={{ whiteSpace: 'pre-wrap' }}>{ck.content}</Typography>
                    </Box>
                  ))}
                  {chunks.length === 0 && (
                    <Typography variant="body2" color="text.secondary">暂无分块，请先注入内容。</Typography>
                  )}
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {loading && (
          <Box sx={{ position: 'fixed', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
            <CircularProgress />
          </Box>
        )}
      </Box>
    </ManagementLayout>
  );
};

export default KnowledgeDocumentDetailPage;

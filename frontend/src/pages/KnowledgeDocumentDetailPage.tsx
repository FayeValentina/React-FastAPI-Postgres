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
  Delete as DeleteIcon,
  Restore as RestoreIcon,
} from '@mui/icons-material';
import ManagementLayout from '../components/Layout/ManagementLayout';
import api from '../services/api';
import { useNotifications } from '../components/Common/NotificationSystem';
import { extractErrorMessage, type ApiError } from '../utils/errorHandler';
import { KnowledgeChunkRead, KnowledgeDocumentRead } from '../types';

type ChunkDraft = {
  content: string;
  chunkIndex: string;
};

const KnowledgeDocumentDetailPage: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { success, error } = useNotifications();

  const docId = useMemo(() => Number(id), [id]);
  const [loading, setLoading] = useState(false);
  const [document, setDocument] = useState<KnowledgeDocumentRead | null>(null);
  const [chunks, setChunks] = useState<KnowledgeChunkRead[]>([]);

  // document editable state
  const [title, setTitle] = useState('');
  const [tagsText, setTagsText] = useState('');
  const [sourceType, setSourceType] = useState('');
  const [sourceRef, setSourceRef] = useState('');
  const [createdBy, setCreatedBy] = useState('');

  // per-chunk editable state
  const [chunkEdits, setChunkEdits] = useState<Record<number, ChunkDraft>>({});
  const [chunkSaving, setChunkSaving] = useState<Record<number, boolean>>({});
  const [chunkDeleting, setChunkDeleting] = useState<Record<number, boolean>>({});
  const [chunkErrors, setChunkErrors] = useState<Record<number, string | null>>({});

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

      // initialise document fields
      setTitle(doc?.title || '');
      setTagsText((doc?.tags || []).join(', '));
      setSourceType(doc?.source_type || '');
      setSourceRef(doc?.source_ref || '');
      setCreatedBy(doc?.created_by || '');

      const drafts: Record<number, ChunkDraft> = {};
      (cks || []).forEach((ck) => {
        drafts[ck.id] = {
          content: ck.content,
          chunkIndex: typeof ck.chunk_index === 'number' ? String(ck.chunk_index) : '',
        };
      });
      setChunkEdits(drafts);
      setChunkSaving({});
      setChunkDeleting({});
      setChunkErrors({});
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

    const tags = tagsText
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    const normalizeOptional = (value: string) => {
      const trimmed = value.trim();
      return trimmed.length > 0 ? trimmed : null;
    };

    const payload: Record<string, unknown> = {};

    if (title !== (document.title || '')) payload.title = title;
    if (JSON.stringify(tags) !== JSON.stringify(document.tags || [])) payload.tags = tags;

    const normalizedSourceType = normalizeOptional(sourceType);
    if (normalizedSourceType !== (document.source_type ?? null)) payload.source_type = normalizedSourceType;

    const normalizedSourceRef = normalizeOptional(sourceRef);
    if (normalizedSourceRef !== (document.source_ref ?? null)) payload.source_ref = normalizedSourceRef;

    const normalizedCreatedBy = normalizeOptional(createdBy);
    if (normalizedCreatedBy !== (document.created_by ?? null)) payload.created_by = normalizedCreatedBy;

    if (Object.keys(payload).length === 0) {
      success('没有检测到可保存的更改');
      return;
    }

    try {
      await api.patch<KnowledgeDocumentRead>(`/v1/knowledge/documents/${document.id}`, payload);
      success('更新成功');
      await loadData();
    } catch (e) {
      error(extractErrorMessage(e as ApiError) || '更新失败');
    }
  };

  const handleChunkReset = (chunkId: number) => {
    const chunk = chunks.find((ck) => ck.id === chunkId);
    if (!chunk) return;
    setChunkEdits((prev) => ({
      ...prev,
      [chunkId]: {
        content: chunk.content,
        chunkIndex: typeof chunk.chunk_index === 'number' ? String(chunk.chunk_index) : '',
      },
    }));
    setChunkErrors((prev) => ({ ...prev, [chunkId]: null }));
  };

  const handleChunkSave = async (chunkId: number) => {
    const chunk = chunks.find((ck) => ck.id === chunkId);
    if (!chunk) return;

    const draft = chunkEdits[chunkId] ?? {
      content: chunk.content,
      chunkIndex: typeof chunk.chunk_index === 'number' ? String(chunk.chunk_index) : '',
    };

    const payload: Record<string, unknown> = {};

    if (draft.content !== chunk.content) {
      payload.content = draft.content;
    }

    const trimmedIndex = draft.chunkIndex.trim();
    let parsedIndex: number | null = null;
    if (trimmedIndex.length > 0) {
      const parsed = Number(trimmedIndex);
      if (!Number.isFinite(parsed) || !Number.isInteger(parsed)) {
        setChunkErrors((prev) => ({ ...prev, [chunkId]: '块序必须为整数' }));
        return;
      }
      parsedIndex = parsed;
    }

    const currentIndex = chunk.chunk_index ?? null;
    if (parsedIndex !== currentIndex) {
      payload.chunk_index = parsedIndex;
    }

    if (Object.keys(payload).length === 0) {
      success('未检测到分块更改');
      return;
    }

    setChunkErrors((prev) => ({ ...prev, [chunkId]: null }));
    setChunkSaving((prev) => ({ ...prev, [chunkId]: true }));
    try {
      const updated = await api.patch<KnowledgeChunkRead>(`/v1/knowledge/chunks/${chunkId}`, payload);
      setChunks((prev) => prev.map((ck) => (ck.id === chunkId ? updated : ck)));
      setChunkEdits((prev) => ({
        ...prev,
        [chunkId]: {
          content: updated.content,
          chunkIndex: typeof updated.chunk_index === 'number' ? String(updated.chunk_index) : '',
        },
      }));
      success('分块更新成功');
    } catch (e) {
      error(extractErrorMessage(e as ApiError) || '更新分块失败');
    } finally {
      setChunkSaving((prev) => ({ ...prev, [chunkId]: false }));
    }
  };

  const handleChunkDelete = async (chunkId: number) => {
    if (!window.confirm('确定删除该分块？')) return;
    setChunkDeleting((prev) => ({ ...prev, [chunkId]: true }));
    try {
      await api.delete(`/v1/knowledge/chunks/${chunkId}`);
      setChunks((prev) => prev.filter((ck) => ck.id !== chunkId));
      setChunkEdits((prev) => {
        const next = { ...prev };
        delete next[chunkId];
        return next;
      });
      setChunkErrors((prev) => {
        const next = { ...prev };
        delete next[chunkId];
        return next;
      });
      success('分块已删除');
    } catch (e) {
      error(extractErrorMessage(e as ApiError) || '删除分块失败');
    } finally {
      setChunkDeleting((prev) => ({ ...prev, [chunkId]: false }));
    }
  };

  const createdAtDisplay = useMemo(() => {
    if (!document?.created_at) return '';
    try {
      return new Date(document.created_at).toLocaleString();
    } catch {
      return document.created_at;
    }
  }, [document?.created_at]);

  return (
    <ManagementLayout>
      <Box>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Button startIcon={<ArrowBackIcon />} onClick={() => navigate('/management/knowledge')}>
              返回
            </Button>
            <Typography variant="h5">文档详情</Typography>
          </Stack>
          <Stack direction="row" spacing={1}>
            <Button
              variant="contained"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              disabled={loading || !document}
            >
              保存
            </Button>
          </Stack>
        </Stack>

        <Grid container spacing={3}>
          <Grid item xs={12} md={5}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  元数据编辑
                </Typography>
                <Stack spacing={2}>
                  <TextField label="标题" value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
                  <TextField
                    label="来源类型 (source_type)"
                    value={sourceType}
                    onChange={(e) => setSourceType(e.target.value)}
                    fullWidth
                  />
                  <TextField
                    label="来源引用 (source_ref)"
                    value={sourceRef}
                    onChange={(e) => setSourceRef(e.target.value)}
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
                    label="创建人 (created_by)"
                    value={createdBy}
                    onChange={(e) => setCreatedBy(e.target.value)}
                    fullWidth
                  />
                  <TextField
                    label="创建时间"
                    value={createdAtDisplay}
                    fullWidth
                    InputProps={{ readOnly: true }}
                    disabled
                  />
                </Stack>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={7}>
            <Card variant="outlined">
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  文本分块管理
                </Typography>
                <Stack spacing={1.5}>
                  {chunks.map((ck) => {
                    const draft = chunkEdits[ck.id] ?? {
                      content: ck.content,
                      chunkIndex: typeof ck.chunk_index === 'number' ? String(ck.chunk_index) : '',
                    };
                    const saving = chunkSaving[ck.id] ?? false;
                    const deleting = chunkDeleting[ck.id] ?? false;
                    const errorMessage = chunkErrors[ck.id] ?? null;

                    return (
                      <Box
                        key={ck.id}
                        sx={{ p: 1.5, borderRadius: 1, border: '1px solid', borderColor: 'divider' }}
                      >
                        <Stack direction="row" spacing={1} sx={{ mb: 0.5 }} alignItems="center">
                          <Chip size="small" label={`#${ck.chunk_index ?? '-'}`} />
                          <Typography variant="caption" color="text.secondary">
                            {new Date(ck.created_at).toLocaleString()}
                          </Typography>
                        </Stack>
                        <Stack spacing={1}>
                          <TextField
                            label="分块内容"
                            value={draft.content}
                            onChange={(e) =>
                              setChunkEdits((prev) => {
                                const existing =
                                  prev[ck.id] ?? {
                                    content: ck.content,
                                    chunkIndex:
                                      typeof ck.chunk_index === 'number'
                                        ? String(ck.chunk_index)
                                        : '',
                                  };
                                return {
                                  ...prev,
                                  [ck.id]: {
                                    ...existing,
                                    content: e.target.value,
                                  },
                                };
                              })
                            }
                            fullWidth
                            multiline
                            minRows={4}
                          />
                          <Stack direction="row" spacing={1} alignItems="flex-start">
                            <TextField
                              label="块序 (可选)"
                              type="number"
                              value={draft.chunkIndex}
                              onChange={(e) => {
                                const value = e.target.value;
                                setChunkEdits((prev) => {
                                  const existing =
                                    prev[ck.id] ?? {
                                      content: ck.content,
                                      chunkIndex:
                                        typeof ck.chunk_index === 'number'
                                          ? String(ck.chunk_index)
                                          : '',
                                    };
                                  return {
                                    ...prev,
                                    [ck.id]: {
                                      ...existing,
                                      chunkIndex: value,
                                    },
                                  };
                                });
                                setChunkErrors((prev) => ({ ...prev, [ck.id]: null }));
                              }}
                              sx={{ width: 150 }}
                              error={Boolean(errorMessage)}
                              helperText={errorMessage ?? '留空表示不指定顺序'}
                            />
                            <Stack direction="row" spacing={1}>
                              <Button
                                variant="contained"
                                size="small"
                                onClick={() => handleChunkSave(ck.id)}
                                disabled={saving || deleting}
                                startIcon={<SaveIcon fontSize="small" />}
                              >
                                保存分块
                              </Button>
                              <Button
                                variant="outlined"
                                size="small"
                                onClick={() => handleChunkReset(ck.id)}
                                disabled={saving || deleting}
                                startIcon={<RestoreIcon fontSize="small" />}
                              >
                                重置
                              </Button>
                              <Button
                                variant="outlined"
                                color="error"
                                size="small"
                                onClick={() => handleChunkDelete(ck.id)}
                                disabled={saving || deleting}
                                startIcon={<DeleteIcon fontSize="small" />}
                              >
                                删除
                              </Button>
                            </Stack>
                          </Stack>
                        </Stack>
                      </Box>
                    );
                  })}
                  {chunks.length === 0 && (
                    <Typography variant="body2" color="text.secondary">
                      暂无分块，请先注入内容。
                    </Typography>
                  )}
                </Stack>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {loading && (
          <Box
            sx={{
              position: 'fixed',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
            }}
          >
            <CircularProgress />
          </Box>
        )}
      </Box>
    </ManagementLayout>
  );
};

export default KnowledgeDocumentDetailPage;

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Stack,
  Typography,
} from '@mui/material';
import {
  Add as AddIcon,
  Refresh as RefreshIcon,
  LibraryBooks as LibraryBooksIcon,
} from '@mui/icons-material';
import ManagementLayout from '../components/Layout/ManagementLayout';
import api from '../services/api';
import { useNotifications } from '../components/Common/NotificationSystem';
import { extractErrorMessage, type ApiError } from '../utils/errorHandler';
import {
  KnowledgeChunkRead,
  KnowledgeDocumentCreate,
  KnowledgeDocumentRead,
  KnowledgeIngestResult,
} from '../types';
import KnowledgeSearch from '../components/Knowledge/KnowledgeSearch';
import DocumentList from '../components/Knowledge/DocumentList';
import CreateDocumentModal from '../components/Knowledge/CreateDocumentModal';
import IngestModal from '../components/Knowledge/IngestModal';
import { useNavigate } from 'react-router-dom';

const KnowledgeBasePage: React.FC = () => {
  const { success, error } = useNotifications();
  const navigate = useNavigate();

  const [documents, setDocuments] = useState<KnowledgeDocumentRead[]>([]);
  const [searchResults, setSearchResults] = useState<KnowledgeChunkRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [ingestOpen, setIngestOpen] = useState(false);
  const [ingestTarget, setIngestTarget] = useState<KnowledgeDocumentRead | null>(null);

  const docsUrl = '/v1/knowledge/documents';

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<KnowledgeDocumentRead[]>(docsUrl);
      setDocuments(data ?? []);
    } catch (e) {
      error(extractErrorMessage(e as ApiError) || '获取文档列表失败');
    } finally {
      setLoading(false);
    }
  }, [docsUrl, error]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleCreate = async (payload: KnowledgeDocumentCreate) => {
    try {
      await api.post<KnowledgeDocumentRead>(docsUrl, payload);
      success('文档创建成功');
      setCreateOpen(false);
      await loadDocuments();
    } catch (e) {
      error(extractErrorMessage(e as ApiError) || '创建文档失败');
    }
  };

  const handleDelete = async (doc: KnowledgeDocumentRead) => {
    if (!window.confirm(`确定删除文档 ID=${doc.id}（${doc.title || '未命名'}）？`)) return;
    try {
      await api.delete(`${docsUrl}/${doc.id}`);
      success('删除成功');
      await loadDocuments();
    } catch (e) {
      error(extractErrorMessage(e as ApiError) || '删除失败');
    }
  };

  const handleOpenIngest = (doc: KnowledgeDocumentRead) => {
    setIngestTarget(doc);
    setIngestOpen(true);
  };

  const handleIngest = async ({ content, file, overwrite }: { content: string; file: File | null; overwrite: boolean }) => {
    if (!ingestTarget) return;
    try {
      let data: KnowledgeIngestResult;
      if (file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('overwrite', overwrite ? 'true' : 'false');
        data = await api.post<KnowledgeIngestResult>(
          `${docsUrl}/${ingestTarget.id}/ingest/upload`,
          formData
        );
      } else {
        data = await api.post<KnowledgeIngestResult>(`${docsUrl}/${ingestTarget.id}/ingest`, {
          content,
          overwrite,
        });
      }
      success(`注入成功，生成 ${data.chunks} 个分块`);
      setIngestOpen(false);
    } catch (e) {
      error(extractErrorMessage(e as ApiError) || '注入失败');
    }
  };

  const handleSearch = async (query: string, topK: number) => {
    setLoading(true);
    try {
      const data = await api.post<KnowledgeChunkRead[]>('/v1/knowledge/search', { query, top_k: topK });
      setSearchResults(data ?? []);
    } catch (e) {
      error(extractErrorMessage(e as ApiError) || '搜索失败');
    } finally {
      setLoading(false);
    }
  };

  const headerActions = useMemo(() => (
    <Stack direction="row" spacing={1}>
      <Button
        variant="outlined"
        startIcon={<RefreshIcon />}
        onClick={loadDocuments}
        disabled={loading}
      >
        刷新
      </Button>
      <Button
        variant="contained"
        startIcon={<AddIcon />}
        onClick={() => setCreateOpen(true)}
      >
        创建文档
      </Button>
    </Stack>
  ), [loadDocuments, loading]);

  return (
    <ManagementLayout>
      <Box>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 3 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <LibraryBooksIcon color="primary" />
            <Typography variant="h4" sx={{ fontSize: { xs: 20, sm: 24, md: 28 } }}>知识库管理</Typography>
          </Stack>
          {headerActions}
        </Stack>

        <Card variant="outlined" sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 2 }}>知识搜索</Typography>
            <KnowledgeSearch onSearch={handleSearch} results={searchResults} loading={loading} />
          </CardContent>
        </Card>

        <Card variant="outlined">
          <CardContent>
          <DocumentList
            documents={documents}
            loading={loading}
            onDelete={handleDelete}
            onIngest={handleOpenIngest}
            onRefresh={loadDocuments}
            onView={(doc) => navigate(`/management/knowledge/${doc.id}`)}
          />
          </CardContent>
        </Card>

        {loading && (
          <Box sx={{ position: 'fixed', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
            <CircularProgress />
          </Box>
        )}

        <CreateDocumentModal
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          onCreate={handleCreate}
        />

        <IngestModal
          open={ingestOpen}
          onClose={() => setIngestOpen(false)}
          onIngest={handleIngest}
          documentTitle={ingestTarget?.title || null}
        />
      </Box>
    </ManagementLayout>
  );
};

export default KnowledgeBasePage;

import React from 'react';
import {
  Box,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  Upload as UploadIcon,
  Refresh as RefreshIcon,
  Visibility as VisibilityIcon,
} from '@mui/icons-material';
import { KnowledgeDocumentRead } from '../../types';

interface DocumentListProps {
  documents: KnowledgeDocumentRead[];
  loading?: boolean;
  onDelete: (doc: KnowledgeDocumentRead) => void;
  onIngest: (doc: KnowledgeDocumentRead) => void;
  onRefresh?: () => void;
  onView?: (doc: KnowledgeDocumentRead) => void;
}

const DocumentList: React.FC<DocumentListProps> = ({ documents, loading, onDelete, onIngest, onRefresh, onView }) => {
  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="h6">文档列表</Typography>
        <Tooltip title="刷新">
          <span>
            <IconButton onClick={onRefresh} disabled={loading}>
              <RefreshIcon />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell width={80}>ID</TableCell>
              <TableCell>标题</TableCell>
              <TableCell width={160}>来源类型</TableCell>
              <TableCell width={220}>来源标识</TableCell>
              <TableCell width={180}>创建时间</TableCell>
              <TableCell width={160} align="right">操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {documents.map((doc) => (
              <TableRow key={doc.id} hover>
                <TableCell>{doc.id}</TableCell>
                <TableCell>{doc.title || '-'}</TableCell>
                <TableCell>{doc.source_type || '-'}</TableCell>
                <TableCell sx={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {doc.source_ref || '-'}
                </TableCell>
                <TableCell>{new Date(doc.created_at).toLocaleString()}</TableCell>
                <TableCell align="right">
                  <Tooltip title="详情">
                    <span>
                      <IconButton onClick={() => onView && onView(doc)} disabled={loading}>
                        <VisibilityIcon />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title="注入内容">
                    <span>
                      <IconButton onClick={() => onIngest(doc)} disabled={loading}>
                        <UploadIcon />
                      </IconButton>
                    </span>
                  </Tooltip>
                  <Tooltip title="删除文档">
                    <span>
                      <IconButton color="error" onClick={() => onDelete(doc)} disabled={loading}>
                        <DeleteIcon />
                      </IconButton>
                    </span>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
            {documents.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography variant="body2" color="text.secondary">暂无文档</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default DocumentList;

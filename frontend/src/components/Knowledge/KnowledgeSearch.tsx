import React, { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  FormControlLabel,
  Switch,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import { KnowledgeSearchResult } from '../../types';

interface KnowledgeSearchProps {
  onSearch: (query: string, topK: number, useBm25: boolean) => Promise<void> | void;
  results: KnowledgeSearchResult[];
  loading?: boolean;
}

const KnowledgeSearch: React.FC<KnowledgeSearchProps> = ({ onSearch, results, loading }) => {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [useBm25, setUseBm25] = useState(true);

  const handleSearch = () => {
    if (!query.trim()) return;
    onSearch(query.trim(), Math.max(1, Math.min(50, Number(topK) || 5)), useBm25);
  };

  return (
    <Box>
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems={{ sm: 'center' }}>
        <TextField
          fullWidth
          label="搜索查询"
          placeholder="输入要检索的内容..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        />
        <TextField
          type="number"
          label="Top K"
          value={topK}
          inputProps={{ min: 1, max: 50 }}
          onChange={(e) => setTopK(Number(e.target.value))}
          sx={{ width: { xs: '100%', sm: 120 } }}
        />
        <FormControlLabel
          control={
            <Switch
              checked={useBm25}
              onChange={(e) => setUseBm25(e.target.checked)}
              color="primary"
            />
          }
          label={useBm25 ? 'BM25' : '向量'}
          sx={{ ml: { sm: 1 } }}
        />
        <Button
          variant="contained"
          startIcon={<SearchIcon />}
          onClick={handleSearch}
          disabled={loading}
        >
          搜索
        </Button>
      </Stack>

      <Divider sx={{ my: 2 }} />

      <Stack spacing={1}>
        {results.map((item) => (
          <Card key={`${item.id}`} variant="outlined">
            <CardContent>
              <Typography variant="caption" color="text.secondary">
                文档ID: {item.document_id ?? '-'} · 块序: {item.chunk_index ?? '-'} · {new Date(item.created_at).toLocaleString()} · 来源: {item.retrieval_source.toUpperCase()}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                Score: {item.score.toFixed(4)} · 相似度: {item.similarity.toFixed(4)}
                {typeof item.bm25_score === 'number' ? ` · BM25: ${item.bm25_score.toFixed(2)}` : ''}
              </Typography>
              <Typography sx={{ mt: 1, whiteSpace: 'pre-wrap' }}>
                {item.content}
              </Typography>
            </CardContent>
          </Card>
        ))}
        {results.length === 0 && (
          <Typography variant="body2" color="text.secondary">无搜索结果</Typography>
        )}
      </Stack>
    </Box>
  );
};

export default KnowledgeSearch;

import React, { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';
import { KnowledgeChunkRead } from '../../types';

interface KnowledgeSearchProps {
  onSearch: (query: string, topK: number) => Promise<void> | void;
  results: KnowledgeChunkRead[];
  loading?: boolean;
}

const KnowledgeSearch: React.FC<KnowledgeSearchProps> = ({ onSearch, results, loading }) => {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);

  const handleSearch = () => {
    if (!query.trim()) return;
    onSearch(query.trim(), Math.max(1, Math.min(50, Number(topK) || 5)));
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
                文档ID: {item.document_id ?? '-'} · 块序: {item.chunk_index ?? '-'} · {new Date(item.created_at).toLocaleString()}
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


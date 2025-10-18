import { useMemo } from 'react';
import {
  Box,
  Button,
  CircularProgress,
  Divider,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import { Add as AddIcon, Refresh as RefreshIcon } from '@mui/icons-material';
import { ConversationListItem } from '../../types';

interface ChatHistoryListProps {
  conversations: ConversationListItem[];
  selectedConversationId: string | null;
  loading?: boolean;
  refreshing?: boolean;
  onSelect: (conversationId: string) => void;
  onCreateConversation: () => void;
  onRefresh?: () => void;
}

const formatRelative = (isoString: string | undefined): string => {
  if (!isoString) {
    return '';
  }
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const diff = Date.now() - date.getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;

  if (diff < minute) return 'just now';
  if (diff < hour) return `${Math.floor(diff / minute)}m ago`;
  if (diff < day) return `${Math.floor(diff / hour)}h ago`;
  return date.toLocaleDateString();
};

export default function ChatHistoryList({
  conversations,
  selectedConversationId,
  loading,
  refreshing,
  onSelect,
  onCreateConversation,
  onRefresh,
}: ChatHistoryListProps) {
  const content = useMemo(() => {
    if (loading) {
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 6 }}>
          <CircularProgress size={28} />
        </Box>
      );
    }

    if (!conversations.length) {
      return (
        <Box sx={{ py: 5, textAlign: 'center', px: 2 }}>
          <Typography variant="body1" sx={{ fontWeight: 600, mb: 1 }}>
            No conversations yet
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Start a new chat to see it listed here.
          </Typography>
          <Button variant="contained" onClick={onCreateConversation} startIcon={<AddIcon />}>
            New Conversation
          </Button>
        </Box>
      );
    }

    return (
      <List
        dense
        disablePadding
        sx={{
          overflowY: 'auto',
          maxHeight: { xs: 280, sm: '60vh', lg: '70vh' },
        }}
      >
        {conversations.map((conversation) => {
          const isActive = conversation.id === selectedConversationId;
          const secondary = conversation.last_message_preview
            ? conversation.last_message_preview
            : 'No messages yet';

          return (
            <ListItemButton
              key={conversation.id}
              selected={isActive}
              onClick={() => onSelect(conversation.id)}
              sx={{
                alignItems: 'flex-start',
                py: 1.25,
                '&.Mui-selected': {
                  bgcolor: 'action.selected',
                  '&:hover': {
                      bgcolor: 'action.selected',
                  },
                },
              }}
            >
              <ListItemText
                primary={
                  <Stack direction="row" justifyContent="space-between" spacing={1}>
                    <Typography
                      variant="subtitle2"
                      sx={{
                        fontWeight: 600,
                        flex: 1,
                        minWidth: 0,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {conversation.title || 'Untitled chat'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1, flexShrink: 0 }}>
                      {formatRelative(conversation.updated_at)}
                    </Typography>
                  </Stack>
                }
                secondary={
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      mt: 0.5,
                      maxHeight: 48,
                      overflow: 'hidden',
                      display: '-webkit-box',
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical',
                    }}
                  >
                    {secondary}
                  </Typography>
                }
              />
            </ListItemButton>
          );
        })}
      </List>
    );
  }, [conversations, loading, onCreateConversation, onSelect, selectedConversationId]);

  return (
    <Paper
      variant="outlined"
      sx={{
        flexShrink: 0,
        width: { xs: '100%', lg: 320 },
        maxWidth: '100%',
        overflow: 'hidden',
        alignSelf: 'stretch',
      }}
    >
      <Stack spacing={1.5} sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Chat History
          </Typography>
          <Stack direction="row" spacing={1}>
            <Tooltip title="Refresh list">
              <span>
                <IconButton size="small" onClick={onRefresh} disabled={refreshing || !onRefresh}>
                  <RefreshIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
            <Button
              variant="contained"
              size="small"
              startIcon={<AddIcon />}
              onClick={onCreateConversation}
              disabled={refreshing}
            >
              New
            </Button>
          </Stack>
        </Stack>
        <Divider />
      </Stack>
      <Box sx={{ px: 1.5, pb: 2 }}>{content}</Box>
    </Paper>
  );
}

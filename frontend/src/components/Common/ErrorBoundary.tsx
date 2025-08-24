import { Component, ErrorInfo, ReactNode } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Alert,
  Collapse,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
  showDetails: boolean;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    showDetails: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, showDetails: false };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    
    this.setState({
      error,
      errorInfo,
    });

    // 调用外部错误处理器
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  private handleRefresh = () => {
    this.setState({
      hasError: false,
      error: undefined,
      errorInfo: undefined,
      showDetails: false,
    });
    
    // 刷新页面
    window.location.reload();
  };

  private handleRetry = () => {
    this.setState({
      hasError: false,
      error: undefined,
      errorInfo: undefined,
      showDetails: false,
    });
  };

  private toggleDetails = () => {
    this.setState(prevState => ({
      showDetails: !prevState.showDetails,
    }));
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '400px',
            p: 3,
          }}
        >
          <Paper
            elevation={3}
            sx={{
              p: 4,
              maxWidth: 600,
              width: '100%',
              textAlign: 'center',
            }}
          >
            <ErrorIcon
              sx={{
                fontSize: 64,
                color: 'error.main',
                mb: 2,
              }}
            />
            
            <Typography variant="h5" component="h2" gutterBottom>
              出现了一些问题
            </Typography>
            
            <Typography variant="body1" color="text.secondary" paragraph>
              很抱歉，应用程序遇到了意外错误。您可以尝试刷新页面或重试。
            </Typography>

            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', mb: 3 }}>
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={this.handleRefresh}
              >
                刷新页面
              </Button>
              <Button
                variant="outlined"
                onClick={this.handleRetry}
              >
                重试
              </Button>
            </Box>

            {/* 错误详情 */}
            {this.state.error && (
              <Box>
                <Button
                  variant="text"
                  size="small"
                  onClick={this.toggleDetails}
                  endIcon={
                    <ExpandMoreIcon
                      sx={{
                        transform: this.state.showDetails ? 'rotate(180deg)' : 'rotate(0deg)',
                        transition: 'transform 0.3s',
                      }}
                    />
                  }
                >
                  {this.state.showDetails ? '隐藏' : '显示'}错误详情
                </Button>
                
                <Collapse in={this.state.showDetails}>
                  <Alert severity="error" sx={{ mt: 2, textAlign: 'left' }}>
                    <Typography variant="subtitle2" gutterBottom>
                      错误信息:
                    </Typography>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', mb: 2 }}>
                      {this.state.error.message}
                    </Typography>
                    
                    {this.state.error.stack && (
                      <>
                        <Typography variant="subtitle2" gutterBottom>
                          错误堆栈:
                        </Typography>
                        <Box
                          component="pre"
                          sx={{
                            fontSize: '0.75rem',
                            fontFamily: 'monospace',
                            overflow: 'auto',
                            maxHeight: '200px',
                            bgcolor: 'grey.100',
                            p: 1,
                            borderRadius: 1,
                          }}
                        >
                          {this.state.error.stack}
                        </Box>
                      </>
                    )}
                  </Alert>
                </Collapse>
              </Box>
            )}
          </Paper>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
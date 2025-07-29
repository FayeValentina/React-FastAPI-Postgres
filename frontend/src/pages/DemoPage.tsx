import React, { useEffect, useState } from "react";
import { useNavigate } from 'react-router-dom';
import { Typography, Button, CircularProgress, Alert, Box } from "@mui/material";
import MainLayout from "../components/Layout/MainLayout";
import { useApiStore } from '../stores/api-store';
import { useAuthStore } from '../stores/auth-store';

interface HelloResponse {
  message: string;
  status: string;
}

const DemoPage: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthStore();
  const [activeResponse, setActiveResponse] = useState<'hello' | 'world'>('hello');
  
  // Use useApiStore directly with selectors
  const helloState = useApiStore(state => 
    state.apiStates['/hello'] || { data: null, loading: false, error: null }
  );
  const worldState = useApiStore(state => 
    state.apiStates['/world'] || { data: null, loading: false, error: null }
  );
  const fetchData = useApiStore(state => state.fetchData);
  
  // Extract data for easier usage
  const { data: helloData, loading: helloLoading, error: helloError } = helloState;
  const { data: worldData, loading: worldLoading, error: worldError } = worldState;

  // 认证检查
  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchData<HelloResponse>('/hello');
    }
  }, [isAuthenticated, fetchData]);

  // 如果未认证，不渲染内容
  if (!isAuthenticated) {
    return null;
  }

  const handleHelloClick = () => {
    setActiveResponse('hello');
    fetchData<HelloResponse>('/hello');
  };

  const handleWorldClick = () => {
    setActiveResponse('world');
    fetchData<HelloResponse>('/world');
  };

  const getCurrentMessage = () => {
    if (activeResponse === 'hello') {
      return (helloData as HelloResponse)?.message;
    }
    return (worldData as HelloResponse)?.message;
  };

  return (
    <MainLayout>
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography variant="h3" gutterBottom>
          FastAPI + React Demo
        </Typography>
        
        <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
          这是一个API测试页面，用于验证前后端连接
        </Typography>
        
        {(helloLoading || worldLoading) ? (
          <CircularProgress />
        ) : (helloError || worldError) ? (
          <Alert severity="error">Error: {helloError?.message || worldError?.message}</Alert>
        ) : (
          <Box sx={{ mt: 4 }}>
            <Typography variant="h5" gutterBottom>
              服务器响应:
            </Typography>
            <Typography variant="body1" sx={{ mb: 3 }}>
              {getCurrentMessage() || "未收到消息"}
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              <Button 
                variant="contained" 
                color="primary"
                onClick={handleHelloClick}
                disabled={helloLoading || worldLoading}
              >
                刷新 Hello 数据
              </Button>
              <Button 
                variant="contained" 
                color="secondary"
                onClick={handleWorldClick}
                disabled={helloLoading || worldLoading}
              >
                获取 World 数据
              </Button>
            </Box>
          </Box>
        )}
      </Box>
    </MainLayout>
  );
};

export default DemoPage;
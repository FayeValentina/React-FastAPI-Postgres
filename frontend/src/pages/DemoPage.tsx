import React, { useEffect, useState } from "react";
import { Typography, Button, CircularProgress, Alert, Box } from "@mui/material";
import MainLayout from "../components/Layout/MainLayout";
import useApi from "../hooks/useApi";

interface HelloResponse {
  message: string;
  status: string;
}

const DemoPage: React.FC = () => {
  const [activeResponse, setActiveResponse] = useState<'hello' | 'world'>('hello');
  const { data: helloData, loading: helloLoading, error: helloError, fetchData: fetchHello } = useApi<HelloResponse>("/hello");
  const { data: worldData, loading: worldLoading, error: worldError, fetchData: fetchWorld } = useApi<HelloResponse>("/world");

  useEffect(() => {
    fetchHello();
  }, [fetchHello]);

  const handleHelloClick = () => {
    setActiveResponse('hello');
    fetchHello();
  };

  const handleWorldClick = () => {
    setActiveResponse('world');
    fetchWorld();
  };

  const getCurrentMessage = () => {
    if (activeResponse === 'hello') {
      return helloData?.message;
    }
    return worldData?.message;
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
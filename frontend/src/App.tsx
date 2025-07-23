import React, { useEffect, useState } from "react";
import { Typography, Button, CircularProgress, Alert, Box } from "@mui/material";
import MainLayout from "./components/Layout/MainLayout";
import useApi from "./hooks/useApi";

interface HelloResponse {
  message: string;
  status: string;
}

const App: React.FC = () => {
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
        
        {(helloLoading || worldLoading) ? (
          <CircularProgress />
        ) : (helloError || worldError) ? (
          <Alert severity="error">Error: {helloError?.message || worldError?.message}</Alert>
        ) : (
          <Box sx={{ mt: 4 }}>
            <Typography variant="h5" gutterBottom>
              Server Response:
            </Typography>
            <Typography variant="body1" sx={{ mb: 3 }}>
              {getCurrentMessage() || "No message received"}
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              <Button 
                variant="contained" 
                color="primary"
                onClick={handleHelloClick}
                disabled={helloLoading || worldLoading}
              >
                Refresh Data
              </Button>
              <Button 
                variant="contained" 
                color="secondary"
                onClick={handleWorldClick}
                disabled={helloLoading || worldLoading}
              >
                World
              </Button>
            </Box>
          </Box>
        )}
      </Box>
    </MainLayout>
  );
};

export default App;
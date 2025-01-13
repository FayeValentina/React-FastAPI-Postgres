import React, { useEffect } from "react";
import { Typography, Button, CircularProgress, Alert, Box } from "@mui/material";
import MainLayout from "./components/Layout/MainLayout";
import useApi from "./hooks/useApi";

interface HelloResponse {
  message: string;
  status: string;
}

const App: React.FC = () => {
  const { data, loading, error, fetchData } = useApi<HelloResponse>("/hello");

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <MainLayout>
      <Box sx={{ textAlign: 'center', py: 4 }}>
        <Typography variant="h3" gutterBottom>
          FastAPI + React Demo
        </Typography>
        
        {loading ? (
          <CircularProgress />
        ) : error ? (
          <Alert severity="error">Error: {error.message}</Alert>
        ) : (
          <Box sx={{ mt: 4 }}>
            <Typography variant="h5" gutterBottom>
              Server Response:
            </Typography>
            <Typography variant="body1" sx={{ mb: 3 }}>
              {data?.message || "No message received"}
            </Typography>
            <Button 
              variant="contained" 
              color="primary"
              onClick={() => fetchData()}
              disabled={loading}
            >
              Refresh Data
            </Button>
          </Box>
        )}
      </Box>
    </MainLayout>
  );
};

export default App;
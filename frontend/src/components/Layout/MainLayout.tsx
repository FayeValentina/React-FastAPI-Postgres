import React from 'react';
import { Container, Box } from '@mui/material';

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Container component="main" sx={{ flex: 1, py: 4 }}>
        {children}
      </Container>
    </Box>
  );
};

export default MainLayout; 
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider, CssBaseline } from '@mui/material'
import { createTheme, responsiveFontSizes } from '@mui/material/styles'
import { useAuthStore } from './stores/auth-store'
import { NotificationProvider } from './components/Common/NotificationSystem'
import AppRoutes from './routes'
import './index.css'

let theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
  typography: {
    fontFamily: '"Inter", "system-ui", "Avenir", "Helvetica", "Arial", sans-serif',
  },
});
theme = responsiveFontSizes(theme);

// 应用启动时初始化认证状态
const initAuth = async () => {
  const authStore = useAuthStore.getState();
  if (authStore.accessToken && !authStore.user) {
    try {
      await authStore.getCurrentUser();
    } catch (error) {
      console.error('Token validation failed:', error);
      authStore.logout();
    }
  }
};

// 执行初始化
initAuth();

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <NotificationProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </NotificationProvider>
    </ThemeProvider>
  </React.StrictMode>,
)

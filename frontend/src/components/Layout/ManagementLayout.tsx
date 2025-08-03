import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Toolbar,
  AppBar,
  Container,
  Button,
  Divider,
} from '@mui/material';
import {
  SmartToy as BotIcon,
  PlayArrow as SessionIcon,
  Article as ContentIcon,
  ArrowBack as ArrowBackIcon,
  Schedule as TaskIcon,
  Dashboard as DashboardIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';

interface ManagementLayoutProps {
  children: React.ReactNode;
}

const DRAWER_WIDTH = 240;

const menuSections = [
  {
    title: '爬虫管理',
    items: [
      {
        text: 'Bot配置',
        icon: <BotIcon />,
        path: '/management/scraper/bots',
        implemented: true,
      },
      {
        text: '会话管理',
        icon: <SessionIcon />,
        path: '/management/scraper/sessions',
        implemented: true,
      },
      {
        text: '内容管理',
        icon: <ContentIcon />,
        path: '/management/scraper/content',
        implemented: false,
      },
    ],
  },
  {
    title: '系统管理',
    items: [
      {
        text: '任务调度',
        icon: <TaskIcon />,
        path: '/management/tasks',
        implemented: true,
      },
      {
        text: '系统监控',
        icon: <DashboardIcon />,
        path: '/management/monitoring',
        implemented: false,
      },
      {
        text: '系统设置',
        icon: <SettingsIcon />,
        path: '/management/settings',
        implemented: false,
      },
    ],
  },
];

const ManagementLayout: React.FC<ManagementLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleMenuClick = (path: string, implemented: boolean) => {
    if (implemented) {
      navigate(path);
    }
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{
          width: `calc(100% - ${DRAWER_WIDTH}px)`,
          ml: `${DRAWER_WIDTH}px`,
        }}
      >
        <Toolbar>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/dashboard')}
            sx={{ mr: 2, color: 'white' }}
          >
            返回仪表板
          </Button>
          <Typography variant="h6" noWrap component="div">
            综合管理系统
          </Typography>
        </Toolbar>
      </AppBar>

      <Drawer
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            boxSizing: 'border-box',
          },
        }}
        variant="permanent"
        anchor="left"
      >
        <Toolbar>
          <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
            管理功能
          </Typography>
        </Toolbar>
        
        <List>
          {menuSections.map((section, sectionIndex) => (
            <React.Fragment key={section.title}>
              {sectionIndex > 0 && <Divider sx={{ my: 1 }} />}
              <ListItem>
                <Typography variant="caption" color="text.secondary" sx={{ px: 2, py: 1 }}>
                  {section.title}
                </Typography>
              </ListItem>
              {section.items.map((item) => (
                <ListItem key={item.text} disablePadding>
                  <ListItemButton
                    selected={location.pathname === item.path}
                    onClick={() => handleMenuClick(item.path, item.implemented)}
                    disabled={!item.implemented}
                    sx={{
                      '&.Mui-selected': {
                        backgroundColor: 'primary.main',
                        color: 'white',
                        '&:hover': {
                          backgroundColor: 'primary.dark',
                        },
                        '& .MuiListItemIcon-root': {
                          color: 'white',
                        },
                      },
                      '&.Mui-disabled': {
                        opacity: 0.5,
                      },
                    }}
                  >
                    <ListItemIcon
                      sx={{
                        color: location.pathname === item.path ? 'white' : 'inherit',
                      }}
                    >
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={item.text}
                      secondary={!item.implemented ? '(即将推出)' : ''}
                    />
                  </ListItemButton>
                </ListItem>
              ))}
            </React.Fragment>
          ))}
        </List>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          bgcolor: 'background.default',
          p: 3,
          width: `calc(100% - ${DRAWER_WIDTH}px)`,
        }}
      >
        <Toolbar />
        <Container maxWidth="xl">
          {children}
        </Container>
      </Box>
    </Box>
  );
};

export default ManagementLayout;
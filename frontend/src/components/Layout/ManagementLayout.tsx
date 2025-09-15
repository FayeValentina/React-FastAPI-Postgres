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
  IconButton,
  useMediaQuery,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Schedule as TaskIcon,
  Dashboard as DashboardIcon,
  Settings as SettingsIcon,
  Menu as MenuIcon,
  Chat as ChatIcon,
  LibraryBooks as LibraryBooksIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';

interface ManagementLayoutProps {
  children: React.ReactNode;
}

const DRAWER_WIDTH = 240;

const menuSections = [
  {
    title: '任务管理',
    items: [
      {
        text: '任务配置',
        icon: <TaskIcon />,
        path: '/management/tasks',
        implemented: true,
      },
      {
        text: '系统监控',
        icon: <DashboardIcon />,
        path: '/management/monitoring',
        implemented: true,
      },
    ],
  },
  {
    title: '知识库',
    items: [
      {
        text: '知识库管理',
        icon: <LibraryBooksIcon />,
        path: '/management/knowledge',
        implemented: true,
      },
    ],
  },
  {
    title: '服务助手',
    items: [
      {
        text: '聊天机器人',
        icon: <ChatIcon />,
        path: '/chat',
        implemented: true,
      },
    ],
  },
  {
    title: '系统管理',
    items: [
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
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = React.useState(false);

  const toggleDrawer = () => setMobileOpen((v) => !v);

  const handleMenuClick = (path: string, implemented: boolean) => {
    if (implemented) {
      navigate(path);
    }
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={isMobile ? undefined : {
          width: `calc(100% - ${DRAWER_WIDTH}px)`,
          ml: `${DRAWER_WIDTH}px`,
        }}
      >
        <Toolbar>
          {isMobile && (
            <IconButton
              edge="start"
              color="inherit"
              aria-label="open menu"
              onClick={toggleDrawer}
              sx={{ mr: 1 }}
            >
              <MenuIcon />
            </IconButton>
          )}
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate('/dashboard')}
            sx={{ mr: 2, color: 'white', display: { xs: 'none', sm: 'inline-flex' } }}
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
        variant={isMobile ? 'temporary' : 'permanent'}
        open={isMobile ? mobileOpen : true}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
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
          p: { xs: 2, md: 3 },
          width: isMobile ? '100%' : `calc(100% - ${DRAWER_WIDTH}px)`,
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

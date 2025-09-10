import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import {
  Alert,
  AlertTitle,
  Stack,
  Slide,
  IconButton,
  Box,
} from '@mui/material';
import {
  Close as CloseIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
} from '@mui/icons-material';

export type NotificationType = 'success' | 'error' | 'warning' | 'info';

export interface Notification {
  id: string;
  type: NotificationType;
  title?: string;
  message: string;
  autoHide?: boolean;
  duration?: number;
  action?: ReactNode;
}

interface NotificationContextType {
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id'>) => string;
  removeNotification: (id: string) => void;
  clearAll: () => void;
  success: (message: string, options?: Partial<Notification>) => string;
  error: (message: string, options?: Partial<Notification>) => string;
  warning: (message: string, options?: Partial<Notification>) => string;
  info: (message: string, options?: Partial<Notification>) => string;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

// eslint-disable-next-line react-refresh/only-export-components
export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};

interface NotificationProviderProps {
  children: ReactNode;
  maxNotifications?: number;
  defaultDuration?: number;
  position?: {
    vertical: 'top' | 'bottom';
    horizontal: 'left' | 'center' | 'right';
  };
}

export const NotificationProvider: React.FC<NotificationProviderProps> = ({
  children,
  maxNotifications = 5,
  defaultDuration = 6000,
  position = { vertical: 'top', horizontal: 'right' },
}) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const generateId = () => `notification-${Date.now()}-${Math.random()}`;

  const addNotification = useCallback((notification: Omit<Notification, 'id'>): string => {
    const id = generateId();
    const newNotification: Notification = {
      ...notification,
      id,
      autoHide: notification.autoHide !== false,
      duration: notification.duration || defaultDuration,
    };

    setNotifications(prev => {
      const updated = [newNotification, ...prev];
      return updated.slice(0, maxNotifications);
    });

    // 自动移除通知
    if (newNotification.autoHide) {
      setTimeout(() => {
        setNotifications(prev => prev.filter(n => n.id !== id));
      }, newNotification.duration);
    }

    return id;
  }, [defaultDuration, maxNotifications]);

  const removeNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(notification => notification.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  const success = useCallback((message: string, options?: Partial<Notification>) => {
    return addNotification({ ...options, type: 'success', message });
  }, [addNotification]);

  const error = useCallback((message: string, options?: Partial<Notification>) => {
    return addNotification({ 
      ...options, 
      type: 'error', 
      message, 
      autoHide: options?.autoHide !== undefined ? options.autoHide : false 
    });
  }, [addNotification]);

  const warning = useCallback((message: string, options?: Partial<Notification>) => {
    return addNotification({ ...options, type: 'warning', message });
  }, [addNotification]);

  const info = useCallback((message: string, options?: Partial<Notification>) => {
    return addNotification({ ...options, type: 'info', message });
  }, [addNotification]);

  const getIcon = (type: NotificationType) => {
    switch (type) {
      case 'success': return <SuccessIcon />;
      case 'error': return <ErrorIcon />;
      case 'warning': return <WarningIcon />;
      case 'info': return <InfoIcon />;
    }
  };

  const contextValue: NotificationContextType = {
    notifications,
    addNotification,
    removeNotification,
    clearAll,
    success,
    error,
    warning,
    info,
  };

  return (
    <NotificationContext.Provider value={contextValue}>
      {children}
      
      {/* 通知显示区域 */}
      <Box
        sx={{
          position: 'fixed',
          top: position.vertical === 'top' ? 24 : 'auto',
          bottom: position.vertical === 'bottom' ? 24 : 'auto',
          left: position.horizontal === 'left' ? 24 : 'auto',
          right: position.horizontal === 'right' ? 24 : 'auto',
          ...(position.horizontal === 'center' && {
            left: '50%',
            transform: 'translateX(-50%)',
          }),
          zIndex: 9999,
          pointerEvents: 'none',
          px: { xs: 2, sm: 0 },
        }}
      >
        <Stack spacing={1} sx={{ width: 'min(92vw, 480px)' }}>
          {notifications.map((notification) => (
            <Slide
              key={notification.id}
              direction={position.horizontal === 'left' ? 'right' : 'left'}
              in={true}
              mountOnEnter
              unmountOnExit
            >
              <Alert
                severity={notification.type}
                icon={getIcon(notification.type)}
                sx={{ pointerEvents: 'auto' }}
                action={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {notification.action}
                    <IconButton
                      size="small"
                      color="inherit"
                      onClick={() => removeNotification(notification.id)}
                    >
                      <CloseIcon fontSize="small" />
                    </IconButton>
                  </Box>
                }
              >
                {notification.title && (
                  <AlertTitle>{notification.title}</AlertTitle>
                )}
                {notification.message}
              </Alert>
            </Slide>
          ))}
        </Stack>
      </Box>
    </NotificationContext.Provider>
  );
};

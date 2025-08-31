import { useEffect, useRef, useState, useCallback } from 'react';

interface UseAutoRefreshOptions {
  interval?: number; // 刷新间隔，毫秒
  enabled?: boolean; // 是否启用自动刷新
  immediate?: boolean; // 是否立即执行一次
}

interface UseAutoRefreshReturn {
  isRunning: boolean;
  start: () => void;
  stop: () => void;
  toggle: () => void;
  refresh: () => void;
  setInterval: (newInterval: number) => void;
}

export const useAutoRefresh = (
  refreshCallback: () => void | Promise<void>,
  options: UseAutoRefreshOptions = {}
): UseAutoRefreshReturn => {
  const {
    interval = 30000, // 默认30秒
    enabled = true,
    immediate = false,
  } = options;

  const [isRunning, setIsRunning] = useState(enabled);
  const [currentInterval, setCurrentInterval] = useState(interval);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const callbackRef = useRef(refreshCallback);

  // 更新回调引用
  useEffect(() => {
    callbackRef.current = refreshCallback;
  }, [refreshCallback]);

  // 清理定时器
  const clearTimer = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // 启动定时器
  const startTimer = useCallback(() => {
    clearTimer();
    if (currentInterval > 0) {
      intervalRef.current = setInterval(() => {
        callbackRef.current();
      }, currentInterval);
    }
  }, [currentInterval, clearTimer]);

  // 手动刷新
  const refresh = useCallback(() => {
    callbackRef.current();
  }, []);

  // 启动自动刷新
  const start = useCallback(() => {
    setIsRunning(true);
  }, []);

  // 停止自动刷新
  const stop = useCallback(() => {
    setIsRunning(false);
  }, []);

  // 切换自动刷新状态
  const toggle = useCallback(() => {
    setIsRunning(prev => !prev);
  }, []);

  // 设置新的刷新间隔
  const setNewInterval = useCallback((newInterval: number) => {
    setCurrentInterval(newInterval);
  }, []);

  // 处理运行状态变化
  useEffect(() => {
    if (isRunning) {
      startTimer();
    } else {
      clearTimer();
    }

    return clearTimer;
  }, [isRunning, startTimer, clearTimer]);

  // 立即执行
  useEffect(() => {
    if (immediate) {
      refresh();
    }
  }, [immediate, refresh]);

  // 清理
  useEffect(() => {
    return clearTimer;
  }, [clearTimer]);

  return {
    isRunning,
    start,
    stop,
    toggle,
    refresh,
    setInterval: setNewInterval,
  };
};
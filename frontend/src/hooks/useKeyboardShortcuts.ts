import { useEffect, useCallback } from 'react';

export interface KeyboardShortcut {
  key: string;
  ctrlKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  metaKey?: boolean;
  preventDefault?: boolean;
  stopPropagation?: boolean;
  callback: (event: KeyboardEvent) => void;
  description?: string;
  disabled?: boolean;
}

export const useKeyboardShortcuts = (shortcuts: KeyboardShortcut[]) => {
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    // 忽略在输入框、文本框等元素中的按键
    const target = event.target as HTMLElement;
    if (
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.contentEditable === 'true'
    ) {
      return;
    }

    for (const shortcut of shortcuts) {
      if (shortcut.disabled) continue;

      const keyMatch = shortcut.key.toLowerCase() === event.key.toLowerCase();
      const ctrlMatch = (shortcut.ctrlKey || false) === event.ctrlKey;
      const shiftMatch = (shortcut.shiftKey || false) === event.shiftKey;
      const altMatch = (shortcut.altKey || false) === event.altKey;
      const metaMatch = (shortcut.metaKey || false) === event.metaKey;

      if (keyMatch && ctrlMatch && shiftMatch && altMatch && metaMatch) {
        if (shortcut.preventDefault !== false) {
          event.preventDefault();
        }
        if (shortcut.stopPropagation !== false) {
          event.stopPropagation();
        }
        
        shortcut.callback(event);
        break;
      }
    }
  }, [shortcuts]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown]);
};

// 常用快捷键组合
export const SHORTCUTS = {
  REFRESH: { key: 'F5', description: '刷新' },
  CTRL_R: { key: 'r', ctrlKey: true, description: '刷新' },
  ESCAPE: { key: 'Escape', description: '取消/关闭' },
  ENTER: { key: 'Enter', description: '确认' },
  SPACE: { key: ' ', description: '播放/暂停' },
  CTRL_S: { key: 's', ctrlKey: true, description: '保存' },
  CTRL_Z: { key: 'z', ctrlKey: true, description: '撤销' },
  CTRL_Y: { key: 'y', ctrlKey: true, description: '重做' },
  DELETE: { key: 'Delete', description: '删除' },
  BACKSPACE: { key: 'Backspace', description: '删除' },
  CTRL_A: { key: 'a', ctrlKey: true, description: '全选' },
  CTRL_C: { key: 'c', ctrlKey: true, description: '复制' },
  CTRL_V: { key: 'v', ctrlKey: true, description: '粘贴' },
  CTRL_X: { key: 'x', ctrlKey: true, description: '剪切' },
  ARROW_UP: { key: 'ArrowUp', description: '向上' },
  ARROW_DOWN: { key: 'ArrowDown', description: '向下' },
  ARROW_LEFT: { key: 'ArrowLeft', description: '向左' },
  ARROW_RIGHT: { key: 'ArrowRight', description: '向右' },
  TAB: { key: 'Tab', description: '切换' },
  SHIFT_TAB: { key: 'Tab', shiftKey: true, description: '反向切换' },
  HOME: { key: 'Home', description: '开始' },
  END: { key: 'End', description: '结束' },
  PAGE_UP: { key: 'PageUp', description: '上一页' },
  PAGE_DOWN: { key: 'PageDown', description: '下一页' },
} as const;
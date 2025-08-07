# 任务管理系统使用指南

## 功能概览

本项目的任务管理系统提供了完整的任务调度、监控和管理功能，包括：

- 📋 **任务调度管理** - 创建、编辑、删除定时任务
- 📊 **系统监控** - 实时监控系统状态和任务执行情况
- 🔄 **批量操作** - 高效管理多个任务
- 🧹 **清理管理** - 自动和手动清理历史数据
- 📈 **数据可视化** - 图表展示执行统计和趋势
- ⚡ **实时刷新** - 自动更新数据，保持信息最新

## 快速开始

### 1. 安装依赖

确保安装了必要的依赖包：

```bash
cd frontend
npm install

# 项目已包含以下重要依赖：
# - @mui/lab: Timeline 组件支持
# - recharts: 图表库
# - @mui/material: UI组件库
```

### 2. 页面访问

- **任务调度管理**: `/management/tasks`
- **系统监控**: `/management/monitoring`

需要超级管理员权限才能访问这些功能。

### 3. 主要功能

#### 任务调度管理 (`/management/tasks`)

**基础功能:**
- 查看所有调度任务列表
- 每个任务显示执行摘要（成功率、平均耗时等）
- 任务状态筛选和搜索
- 单个任务的启停、删除操作

**高级功能:**
- 🔄 **批量操作**: 选择多个任务进行批量暂停、恢复、删除
- 🔧 **高级批量更新**: 批量修改任务配置（触发器、超时时间等）
- 🧹 **清理管理**: 配置自动清理策略，手动触发清理
- 📊 **任务详情**: 查看任务的详细信息、执行历史、事件记录

**键盘快捷键:**
- `F5` 或 `Ctrl+R`: 刷新任务列表
- `Space`: 切换自动刷新开关
- `Ctrl+B`: 切换批量操作模式
- `Escape`: 关闭对话框或退出批量模式

#### 系统监控 (`/management/monitoring`)

**监控面板:**
- 📈 **系统概览**: 总任务数、活跃任务、健康评分
- 🏃 **活跃任务**: 实时显示正在运行的Celery任务
- 📅 **调度事件**: 任务执行事件的时间线和表格视图
- 📊 **执行统计**: 多维度图表分析执行趋势
- 🔍 **系统分析**: 深度分析调度分布和性能优化建议

**数据可视化:**
- 面积图显示成功/失败趋势
- 折线图展示成功率变化
- 柱状图分析平均执行时间
- 进度条可视化成功率和系统健康度

## 核心特性

### 1. 自动刷新系统

```typescript
// 使用自动刷新Hook
const autoRefresh = useAutoRefresh(refreshCallback, {
  interval: 30000, // 30秒间隔
  enabled: true,   // 默认启用
  immediate: true  // 立即执行一次
});
```

**特点:**
- 可配置刷新间隔（10秒-10分钟）
- 支持启用/暂停自动刷新
- 手动刷新功能
- 智能状态管理

### 2. 批量操作系统

**步骤化操作流程:**
1. **选择任务** - 多选需要操作的任务
2. **配置操作** - 设置更新参数（支持多种操作类型）
3. **预览更改** - 确认操作前完整预览
4. **执行结果** - 详细的执行状态反馈

**支持的操作类型:**
- 设置触发器（Cron表达式、固定间隔）
- 修改最大实例数、超时时间、重试次数
- 批量启用/禁用任务

### 3. 清理管理系统

**三种清理方式:**
- **手动清理**: 即时清理指定天数的历史数据
- **调度清理**: 设置定期自动清理任务
- **清理历史**: 查看历史清理记录和效果

### 4. 数据可视化

**图表类型:**
- **面积图**: 成功/失败执行趋势
- **折线图**: 成功率变化趋势  
- **柱状图**: 平均执行时间分析
- **时间线**: 事件历史可视化

### 5. 错误处理和用户体验

**错误边界:**
```typescript
<ErrorBoundary>
  <YourComponent />
</ErrorBoundary>
```

**加载状态:**
```typescript
<LoadingState 
  type="card" 
  count={6} 
  message="正在加载..." 
/>
```

**通知系统:**
```typescript
const { success, error, warning, info } = useNotifications();

// 显示成功通知
success('任务创建成功！');

// 显示错误通知（不自动隐藏）
error('操作失败，请重试', { autoHide: false });
```

## 键盘快捷键

### 全局快捷键
- `F5`: 刷新当前页面
- `Ctrl+R`: 刷新当前页面
- `Escape`: 关闭对话框/退出当前模式

### 任务管理页面
- `Space`: 切换自动刷新
- `Ctrl+B`: 切换批量操作模式

### 对话框内
- `Enter`: 确认操作
- `Escape`: 关闭对话框

## 技术架构

### 前端技术栈
- **React 18** + **TypeScript**
- **Material-UI v6** + **MUI Lab**
- **Recharts** (图表库)
- **Zustand** (状态管理)
- **React Router v7**

### 状态管理模式
```typescript
// API状态管理
const { fetchData, getApiState } = useApiStore();
const { loading, error } = getApiState(apiUrl);

// 自动刷新管理
const autoRefresh = useAutoRefresh(callback, options);

// 通知管理
const { success, error } = useNotifications();
```

### 组件结构
```
src/
├── components/
│   ├── Common/           # 通用组件
│   │   ├── AutoRefreshControl.tsx
│   │   ├── LoadingState.tsx
│   │   ├── ErrorBoundary.tsx
│   │   └── NotificationSystem.tsx
│   └── Tasks/            # 任务相关组件
│       ├── TaskCard.tsx
│       ├── TaskDetailDialog.tsx
│       ├── ActiveTasksPanel.tsx
│       ├── ScheduleEventsPanel.tsx
│       ├── ExecutionStatsPanel.tsx
│       ├── SystemAnalysisPanel.tsx
│       ├── CleanupManagerDialog.tsx
│       └── BatchUpdateDialog.tsx
├── hooks/                # 自定义Hooks
│   ├── useAutoRefresh.ts
│   └── useKeyboardShortcuts.ts
├── pages/                # 页面组件
│   ├── TaskManagementPage.tsx
│   └── SystemMonitoringPage.tsx
└── types/                # 类型定义
    └── task.ts
```

## 最佳实践

### 1. 性能优化
- 使用 `React.memo` 优化组件渲染
- 合理设置自动刷新间隔
- 分页加载大量数据

### 2. 用户体验
- 提供加载状态反馈
- 错误信息友好提示
- 键盘快捷键支持
- 操作前预览确认

### 3. 数据管理
- 统一的API状态管理
- 错误边界保护
- 自动重试机制

### 4. 可访问性
- 完整的键盘导航支持
- 语义化HTML结构
- 屏幕阅读器友好

## 故障排查

### 常见问题

**1. 图表不显示**
```bash
# 确保安装了 recharts
npm install recharts
```

**2. Timeline组件报错**
```bash  
# 确保安装了 @mui/lab
npm install @mui/lab
```

**3. 自动刷新不工作**
- 检查用户权限（需要超级管理员）
- 查看浏览器控制台错误信息
- 确认API端点可访问

**4. 批量操作失败**
- 检查选中的任务状态
- 查看网络请求错误
- 确认操作权限

### 开发调试

```typescript
// 启用详细日志
localStorage.setItem('debug', 'task-management:*');

// 查看API状态
console.log(useApiStore.getState());

// 查看自动刷新状态  
console.log('Auto refresh running:', autoRefresh.isRunning);
```

## 更新日志

### v2.0.0 (最新)
- ✨ 添加系统监控页面
- 🎨 重构任务管理界面
- 📊 集成数据可视化图表
- 🔄 实现自动刷新系统
- 🧹 添加清理管理功能
- ⚡ 优化用户体验和性能
- 🎯 支持批量操作和高级配置
- ⌨️ 添加键盘快捷键支持

---

## 联系支持

如有问题或建议，请通过以下方式联系：
- 📧 技术支持邮箱
- 🐛 GitHub Issues
- 📚 项目文档
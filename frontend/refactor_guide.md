# React项目架构重构指南 - 分离axios拦截器与状态管理

## 1. 当前架构问题分析

### 1.1 主要问题
- **违反单一职责原则**: `frontend/src/stores/auth-store.ts` 同时承担了状态管理和HTTP拦截器配置的职责
- **代码耦合度过高**: axios拦截器逻辑与Zustand状态管理紧密耦合
- **测试困难**: 无法独立测试拦截器逻辑和状态管理逻辑
- **维护性差**: 修改拦截器可能影响状态管理，代码组织不清晰

### 1.2 具体问题位置
在 `frontend/src/stores/auth-store.ts` 文件中：
- 第580-700行左右的axios拦截器配置代码不应该存在于状态管理文件中
- 全局变量 `refreshPromise` 和 `failedQueue` 的管理逻辑应该封装
- token刷新协调逻辑应该从状态管理中分离

在 `frontend/src/stores/api-store.ts` 文件中：
- `useApiState` helper函数违背了Zustand的设计哲学
- 该函数增加了不必要的抽象层，应直接使用store

## 2. 重构目标
- 实现关注点分离：状态管理、HTTP配置、拦截器逻辑各司其职
- 提高代码可测试性和可维护性
- 保持现有功能不变，只重构架构

## 3. 新增文件清单

### 3.1 创建服务层目录结构
```
frontend/src/services/
├── interceptors.ts     # HTTP拦截器管理
├── authManager.ts      # 认证逻辑管理器
├── uiManager.ts        # UI交互管理器
└── index.ts           # 服务层统一导出
```

### 3.2 新增文件详细说明

#### 3.2.1 `frontend/src/services/interceptors.ts`
**功能**: 管理axios请求和响应拦截器
**职责**: 
- token自动添加到请求头
- 401错误处理和token刷新
- 请求队列管理
- 拦截器的统一配置

#### 3.2.2 `frontend/src/services/authManager.ts`
**功能**: 提供认证相关的操作接口
**职责**:
- 从auth store获取token信息
- 判断是否需要刷新token
- 执行token刷新操作
- 清理认证状态

#### 3.2.3 `frontend/src/services/uiManager.ts` 
**功能**: 管理与认证相关的UI交互
**职责**:
- 显示token过期对话框
- 其他认证相关的UI操作

#### 3.2.4 `frontend/src/services/index.ts`
**功能**: 服务层统一导出文件
**职责**: 导出所有服务层模块

## 4. 需要删除的代码部分

### 4.1 从 `frontend/src/stores/auth-store.ts` 删除以下内容

#### 4.1.1 删除全局变量 (约在文件第550行之后)
```typescript
// 删除这些全局变量
let refreshPromise: Promise<TokenResponse> | null = null;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (error?: unknown) => void;
}> = [];
```

#### 4.1.2 删除辅助函数 (约在文件第560-600行)
```typescript
// 删除这些函数
const processQueue = (error: Error | null, token: string | null = null) => { ... };
const isTokenExpired = (token: string): boolean => { ... };
const getTokenExpiryTime = (token: string): number | null => { ... };
```

#### 4.1.3 删除axios拦截器配置 (约在文件第600行之后到文件末尾)
```typescript
// 删除所有axios拦截器配置代码
api.interceptors.request.use(...);
api.interceptors.response.use(...);
```

**注意**: 保留 `isTokenExpired` 和 `getTokenExpiryTime` 函数的逻辑，但需要移动到合适的位置。

### 4.2 从 `frontend/src/stores/api-store.ts` 删除以下内容

#### 4.2.1 删除useApiState helper函数 (约在文件末尾)
```typescript
// 删除这个违背Zustand设计哲学的helper函数
export const useApiState = <T = unknown>(url: string): ApiState<T> & { fetchData: () => Promise<T> } => {
  const store = useApiStore();
  const apiState = store.apiStates[url] || { data: null, loading: false, error: null };
  
  return {
    data: apiState.data as T | null,
    loading: apiState.loading,
    error: apiState.error,
    fetchData: () => store.fetchData<T>(url),
  };
};
```

### 4.3 从 `frontend/src/stores/index.ts` 删除相关导出
```typescript
// 删除 useApiState 的导出
export { useApiStore, useApiState } from './api-store'; // 改为：
export { useApiStore } from './api-store';
```

## 5. 代码迁移详细指南

### 5.1 创建 `frontend/src/services/interceptors.ts`

#### 5.1.1 迁移内容
将以下逻辑从 `auth-store.ts` 迁移到此文件：
- token过期检查逻辑 (`isTokenExpired`, `getTokenExpiryTime`)
- 请求队列管理逻辑 (`processQueue`, `failedQueue`)
- token刷新协调逻辑 (`refreshPromise`)
- axios请求拦截器逻辑
- axios响应拦截器逻辑

#### 5.1.2 新增内容
- `InterceptorManager` 类封装所有拦截器逻辑
- `setupInterceptors` 函数用于初始化拦截器
- 通过依赖注入的方式与auth store和UI store交互

### 5.2 创建 `frontend/src/services/authManager.ts`

#### 5.2.1 实现功能
- 提供访问auth store的统一接口
- 封装token相关的操作逻辑
- 不直接依赖store实现，而是通过接口调用

### 5.3 创建 `frontend/src/services/uiManager.ts`

#### 5.3.1 实现功能 
- 封装UI相关的操作
- 提供显示token过期对话框的接口

### 5.4 修改 `frontend/src/services/api.ts`

#### 5.4.1 添加内容
在现有api配置之后添加：
```typescript
import { setupInterceptors } from './interceptors';

// 在创建api实例后添加
setupInterceptors(api);
```

#### 5.4.2 保持原有内容
- 保持现有的axios实例配置不变
- 保持baseURL和headers配置不变

### 5.5 修改 `frontend/src/pages/DemoPage.tsx`

#### 5.5.1 替换useApiState的使用
将：
```typescript
// ❌ 删除这种使用方式
import { useApiState } from '../stores/api-store';
const { data: helloData, loading: helloLoading, error: helloError, fetchData: fetchHello } = useApiState<HelloResponse>("/hello");
```

改为：
```typescript
// ✅ 直接使用zustand store
import { useApiStore } from '../stores/api-store';
const { apiStates, fetchData } = useApiStore();
const helloState = apiStates['/hello'] || { data: null, loading: false, error: null };
const handleFetchHello = () => fetchData<HelloResponse>('/hello');
```

或使用selector（推荐）：
```typescript
// ✅ 使用selector的方式
const helloState = useApiStore(state => 
  state.apiStates['/hello'] || { data: null, loading: false, error: null }
);
const fetchData = useApiStore(state => state.fetchData);
```

## 6. 具体实施步骤

### 6.1 第一步：创建新文件
1. 创建 `frontend/src/services/authManager.ts`
2. 创建 `frontend/src/services/uiManager.ts` 
3. 创建 `frontend/src/services/interceptors.ts`
4. 创建 `frontend/src/services/index.ts`

### 6.2 第二步：实现新文件内容
按照下面的顺序实现：
1. 先实现 `authManager.ts` 和 `uiManager.ts`（依赖最少）
2. 再实现 `interceptors.ts`（依赖前两个文件）
3. 最后实现 `index.ts`（导出所有服务）

### 6.3 第三步：修改现有文件
1. 修改 `frontend/src/services/api.ts`，添加拦截器初始化
2. 修改 `frontend/src/stores/auth-store.ts`，删除拦截器相关代码
3. 修改 `frontend/src/stores/api-store.ts`，删除 `useApiState` helper函数
4. 修改 `frontend/src/stores/index.ts`，删除 `useApiState` 的导出
5. 修改 `frontend/src/pages/DemoPage.tsx`，调整API调用方式为直接使用store

### 6.4 第四步：验证功能
1. 确保登录功能正常
2. 确保token自动刷新功能正常
3. 确保401错误处理正常
4. 确保token过期对话框正常显示

## 7. 重要注意事项

### 7.1 依赖关系
- `interceptors.ts` 依赖 `authManager.ts` 和 `uiManager.ts`
- `authManager.ts` 依赖 `auth-store.ts`
- `uiManager.ts` 依赖 `ui-store.ts`
- 避免循环依赖

### 7.2 功能保持
- 所有现有认证功能必须保持不变
- token刷新逻辑必须完全保持
- 错误处理逻辑必须完全保持

### 7.3 类型安全
- 确保所有新文件都有完整的TypeScript类型定义
- 确保接口定义清晰
- 确保没有any类型的使用

## 8. 文件间的具体迁移映射

### 8.1 从 `auth-store.ts` 到 `interceptors.ts`
- `refreshPromise` → `InterceptorManager.refreshPromise`
- `failedQueue` → `InterceptorManager.failedQueue` 
- `processQueue` → `InterceptorManager.processQueue`
- `api.interceptors.request.use` → `InterceptorManager.setupRequestInterceptor`
- `api.interceptors.response.use` → `InterceptorManager.setupResponseInterceptor`

### 8.2 从 `auth-store.ts` 到 `authManager.ts`
- token获取逻辑 → `AuthManager.getAccessToken`
- token有效性检查 → `AuthManager.isTokenValid`
- token刷新需求判断 → `AuthManager.shouldRefreshToken`
- token刷新执行 → `AuthManager.refreshToken`

### 8.3 从拦截器代码到 `uiManager.ts`
- `useUIStore.getState().showTokenExpiryDialog()` → `UIManager.showTokenExpiryDialog`

### 8.4 `api-store.ts` 的简化
- 删除 `useApiState` helper函数（直接使用store）
- 删除相关导出项目
- 在使用处改为直接调用 `useApiStore()` 或使用selector

## 9. 实现模板结构

### 9.1 `authManager.ts` 基本结构
```typescript
export class AuthManager {
  getAccessToken(): string | null
  hasRefreshToken(): boolean  
  shouldRefreshToken(): boolean
  async refreshToken(): Promise<any>
  clearAuth(): void
  isTokenValid(): boolean
  getTokenTimeRemaining(): number
}
```

### 9.2 `interceptors.ts` 基本结构
```typescript
class InterceptorManager {
  private refreshPromise: Promise<any> | null
  private failedQueue: FailedRequest[]
  
  constructor(authManager: AuthManager, uiManager: UIManager)
  setupRequestInterceptor(api: AxiosInstance)
  setupResponseInterceptor(api: AxiosInstance)
  private processQueue(error: Error | null, token?: string | null)
}

export function setupInterceptors(api: AxiosInstance)
```

### 9.3 `uiManager.ts` 基本结构
```typescript
export class UIManager {
  showTokenExpiryDialog(): void
}
```

## 10. 验证重构成功的标准

1. **功能完整性**: 所有认证相关功能正常工作
2. **代码分离**: 状态管理和HTTP配置完全分离
3. **可测试性**: 可以独立测试每个模块
4. **类型安全**: 没有TypeScript编译错误
5. **运行正常**: 应用启动和运行无错误
6. **符合Zustand哲学**: 直接使用store，无多余的helper抽象层
7. **API调用正常**: DemoPage中的API调用功能保持正常

重构完成后：
- `auth-store.ts` 应该只包含纯粹的状态管理逻辑，不再有任何axios相关的代码
- `api-store.ts` 应该只包含基础的API状态管理，不包含helper函数
- 组件中直接使用 `useApiStore()` 或selector，符合Zustand的设计理念
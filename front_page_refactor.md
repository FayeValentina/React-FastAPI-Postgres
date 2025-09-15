-----

### **知识库前端页面 - 实装大纲 (修订版)**

#### **总体目标**

遵循现有项目的设计模式，在 `frontend/src/pages/` 目录下创建一个新的页面，该页面将独立负责与知识库后端的全部交互，并管理其自身的状态。

-----

#### **第一步：定义前端数据类型**

在与后端交互之前，首先要在前端定义好相应的数据结构。

1.  **创建类型文件**: 在 `frontend/src/types/` 目录下创建一个新文件，例如 `knowledge.ts`。

2.  **定义接口 (Interfaces)**: 在 `knowledge.ts` 文件中，根据后端 `schemas.py` 的定义，创建对应的 TypeScript 接口。

    ```typescript
    // frontend/src/types/knowledge.ts
    export interface KnowledgeDocumentRead {
        //请创建与后端对应的内容
    }

    export interface KnowledgeDocumentIngestRequest {
        //请创建与后端对应的内容
    }

    export interface KnowledgeChunkRead {
        //请创建与后端对应的内容
    }

    //...其它对应的schema
    
    // 同时更新 frontend/src/types/index.ts 导出这些新类型
    // export * from './knowledge';
    ```

-----

#### **第二步：创建知识库主页面**

这是所有功能的核心。我们将在这里处理数据获取、状态管理和UI渲染。

1.  **创建页面文件**: 在 `frontend/src/pages/` 目录下创建 `KnowledgeBasePage.tsx`。

2.  **页面结构和逻辑**:

    ```tsx
    // frontend/src/pages/KnowledgeBasePage.tsx
    import React, { useState, useEffect, useCallback } from 'react';
    import { apiClient } from '../services/api'; // 引入 apiClient 实例
    import { uiManager } from '../services/uiManager'; // 用于显示通知
    import { errorHandler } from '../utils/errorHandler'; // 用于错误处理
    import { KnowledgeDocumentRead, KnowledgeChunkRead } from '../types'; // 引入我们刚定义的类型

    // 引入你的UI组件库，例如 antd, MUI, etc.
    // import { Button, Table, Input, Modal, Form, Spin } from 'your-ui-library';

    // 可以在此文件中直接创建子组件，或者从 ../components/Knowledge/ 导入
    // import { DocumentList } from '../components/Knowledge/DocumentList';
    // import { KnowledgeSearch } from '../components/Knowledge/KnowledgeSearch';

    const KnowledgeBasePage: React.FC = () => {
      // --- 状态管理 ---
      const [documents, setDocuments] = useState<KnowledgeDocumentRead[]>([]);
      const [searchResults, setSearchResults] = useState<KnowledgeChunkRead[]>([]);
      const [isLoading, setIsLoading] = useState(false);
      const [isModalVisible, setIsModalVisible] = useState(false);
      // ... 其他需要的状态

      // --- API 调用逻辑 ---

      // 获取所有文档
      const fetchDocuments = useCallback(async () => {
        setIsLoading(true);
        try {
          const response = await apiClient.get<KnowledgeDocumentRead[]>('/knowledge/documents');
          setDocuments(response.data);
        } catch (error) {
          errorHandler(error, '获取文档列表失败');
        } finally {
          setIsLoading(false);
        }
      }, []);

      // 页面加载时自动获取文档列表
      useEffect(() => {
        fetchDocuments();
      }, [fetchDocuments]);

      // 处理文档创建
      const handleCreateDocument = async (values: { title: string }) => {
        try {
          await apiClient.post('/knowledge/documents', { title: values.title });
          uiManager.notifySuccess('文档创建成功');
          setIsModalVisible(false);
          fetchDocuments(); // 成功后刷新列表
        } catch (error) {
          errorHandler(error, '创建文档失败');
        }
      };

      // 处理搜索
      const handleSearch = async (query: string) => {
        if (!query.trim()) return;
        setIsLoading(true);
        try {
            const response = await apiClient.post<KnowledgeChunkRead[]>('/knowledge/search', { query });
            setSearchResults(response.data);
        } catch (error) {
            errorHandler(error, '搜索失败');
        } finally {
            setIsLoading(false);
        }
      };

      // ... 其他API调用函数 (删除, 注入等)

      // --- UI 渲染 ---
      return (
        <div>
          <h1>知识库管理</h1>

          {/* Section 1: 搜索区域 */}
          <div /* KnowledgeSearch Component */>
            {/* 搜索输入框和按钮，调用 handleSearch */}
            {/* ... */}
            {/* 显示 searchResults 的列表 */}
          </div>

          <hr />

          {/* Section 2: 文档列表区域 */}
          <div /* DocumentList Component */>
            <button onClick={() => setIsModalVisible(true)}>创建新文档</button>
            {/* 显示文档列表的表格，数据源是 `documents` */}
            {/* 表格的操作列包含删除、详情等按钮 */}
          </div>

          {/* Section 3: 创建文档的模态框 */}
          <div /* CreateDocumentModal Component */>
            {/* 模态框，包含一个表单，提交时调用 handleCreateDocument */}
          </div>
        </div>
      );
    };

    export default KnowledgeBasePage;
    ```

-----

#### **第三步：创建独立的子组件 (可选但推荐)**

为了保持 `KnowledgeBasePage.tsx` 的整洁，您可以将UI的各个部分拆分成独立的组件。

1.  **创建组件目录**: 在 `frontend/src/components/` 下创建新目录 `Knowledge`。

2.  **创建组件文件**:

      * `KnowledgeSearch.tsx`: 接收一个 `onSearch` 函数作为 prop。
      * `DocumentList.tsx`: 接收 `documents` 数组和 `onDelete` 函数作为 props。
      * `CreateDocumentModal.tsx`: 接收 `visible`, `onCancel`, 和 `onCreate` 函数作为 props。

    这种模式下，**所有API调用和状态管理依然保留在父组件 `KnowledgeBasePage.tsx` 中**。子组件只负责接收数据和回调函数，是纯粹的UI展示组件。

-----

#### **第四步：配置路由**

最后一步是让用户能够访问到我们新创建的页面。

1.  **编辑路由文件**: 打开 `frontend/src/routes.tsx`。

2.  **添加新路由**: 在 `ManagementLayout` 或其他合适的布局下添加新页面的路由。

    ```tsx
    // frontend/src/routes.tsx
    // ...
    import KnowledgeBasePage from './pages/KnowledgeBasePage'; // 引入页面

    // ...
    // 在 managementRoutes 或其他路由数组中添加
    {
        path: 'knowledge',
        element: <KnowledgeBasePage />,
    },
    // ...
    ```

3.  **更新导航菜单**: 在 `frontend/src/components/Layout/ManagementLayout.tsx` (或您使用的布局组件) 的侧边栏或导航栏中，添加入口链接。

    ```tsx
    // ...
    <Link to="/management/knowledge">知识库管理</Link>
    // ...
    ```

-----

这个修订后的大纲完全遵循了您项目中“逻辑和状态保留在页面级组件”的设计哲学，确保了新功能与现有代码库的风格保持一致。
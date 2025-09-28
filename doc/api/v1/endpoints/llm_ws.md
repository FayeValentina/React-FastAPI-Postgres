# `llm_ws.py` (endpoints) 文档

此文件定义了一个核心的WebSocket端点，用于实现与大语言模型（LLM）的流式、有状态、支持RAG（检索增强生成）的实时聊天功能。

## Router 配置
- **`prefix`**: `/ws`
- **`tags`**: `["llm"]`

## WebSocket Endpoint: `ws /chat`

这是一个长连接端点，允许客户端与服务器进行双向实时通信。

### 连接与认证
- **依赖**: `Depends(get_current_user_from_ws)`
- **逻辑**: 在接受WebSocket连接之前，FastAPI会先执行 `get_current_user_from_ws` 依赖。这个依赖会从WebSocket的查询参数或HTTP头中提取并验证JWT令牌，确保只有已认证的用户才能建立连接。如果认证失败，连接将被拒绝。

### 消息处理循环
连接成功后，服务器进入一个无限循环 (`while True`)，等待并处理来自客户端的JSON消息。

#### 1. 接收用户输入
- 服务器等待 `ws.receive_json()`。
- **重置会话**: 如果收到的消息是 `{"type": "reset"}`，服务器会清空当前会话的聊天历史 `history`，并向客户端回送一个确认消息。
- **获取用户问题**: 从消息中提取 `content`（用户问题）和 `temperature`（LLM的温度参数）。

#### 2. RAG - 检索阶段
- **动态配置**: 从 `dynamic_settings_service` 获取最新的RAG配置。
- **策略解析**: 调用 `resolve_rag_parameters`，这是一个高级函数，它可能会根据用户问题、用户角色、动态配置等上下文，决定是否需要改写查询、调整 `top_k` 值或启用/禁用某些RAG策略。
- **执行检索**: 调用 `knowledge_base_service.search_similar_chunks`，使用（可能已被改写的）查询和最终确定的 `top_k` 值，从知识库中检索最相关的知识区块。
- **发送引用**: 将检索到的区块信息（ID、标题、来源、相似度得分、内容片段等）格式化后，通过 `ws.send_json({"type": "citations", ...})` 发送给前端。这使得前端可以在LLM生成回答的同时，向用户展示相关的参考文献。

#### 3. LLM - 生成阶段
- **构建提示 (Prompt)**: 调用 `llm_service.prepare_system_and_user`，将用户的原始问题和检索到的知识区块（“证据”）打包成一个结构化的、包含明确指令的 `system_prompt` 和 `user_prompt`。
- **维护历史**: 将最终的用户提示添加到 `history` 列表中，并确保历史记录不超过 `MAX_HISTORY_MESSAGES` 的长度，以控制上下文窗口的大小。
- **调用LLM API**: 
    - 使用 `client.chat.completions.create` 并设置 `stream=True`，以流式方式调用LLM API。
    - 请求的消息体包含 `system_prompt` 和整个 `history`。
- **流式响应**: 
    - `async for chunk in stream:`: 异步遍历从LLM返回的数据流。
    - **发送Delta**: 对于流中的每一个数据块（`chunk`），提取其中的文本片段（`token`），并通过 `ws.send_json({"type": "delta", "content": token})` 实时地发送给前端。这使得用户可以像在ChatGPT中一样，看到回答被一个词一个词地生成出来。
- **结束与更新历史**: 
    - 流结束后，将所有收到的文本片段拼接成完整的回答。
    - 将LLM的完整回答作为 `assistant` 角色添加到 `history` 中，为下一轮对话做准备。
    - 发送一个 `{"type": "done"}` 消息，通知前端本次回答已全部生成完毕。

### 异常处理
- **`WebSocketDisconnect`**: 如果客户端主动断开连接，服务器会捕获此异常并静默地结束循环，清理资源。
- **其他异常**: 在与LLM API交互等步骤中如果发生错误，会向客户端发送一个 `{"type": "error", ...}` 消息，方便前端进行错误提示。

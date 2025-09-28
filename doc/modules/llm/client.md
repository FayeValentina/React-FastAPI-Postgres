# `client.py` (llm) 文档

此文件负责创建和配置与大语言模型（LLM）服务进行交互的客户端实例。

## 设计理念

- **集中配置**: 将所有LLM客户端的初始化集中在一个地方，使得配置的修改和管理变得简单。
- **多客户端支持**: 它展示了如何根据不同的服务需求（如聊天、分类）配置多个不同的客户端实例。
- **兼容OpenAI SDK**: 尽管后端的LLM服务可能是自托管的（如 `vLLM`, `TGI`）或第三方的（如 `Groq`, `Together AI`），但只要这些服务提供了与OpenAI API兼容的接口，就可以使用官方的 `openai` Python库来与它们进行交互。这极大地简化了客户端的实现。

## 客户端实例

### `client: AsyncOpenAI`
- **用途**: 这是用于**主要聊天功能**的客户端。
- **配置**:
    - `base_url=settings.CHAT_BASE_URL`: API的基础URL。它从应用的配置中读取，指向主聊天模型的服务地址（例如 `https://generativelanguage.googleapis.com/v1beta/openai/`）。
    - `api_key=settings.CHAT_API_KEY`: API密钥。同样从配置中读取。
- **类型**: `AsyncOpenAI`，表示这是一个异步客户端，所有API调用都将是 `async` 的，与FastAPI的事件循环兼容。

### `classifier_client: AsyncOpenAI`
- **用途**: 这是一个专门用于**分类任务**的客户端。
- **配置**:
    - `base_url=settings.CLASSIFIER_BASE_URL`: 指向一个专门用于文本分类的LLM服务的地址（例如 `http://clf_server:8080/v1`）。这表明系统可能使用了一个更小、更专注的模型来处理分类任务，以提高效率和降低成本。
    - `api_key=settings.CLASSIFIER_API_KEY`: 该分类服务所使用的API密钥。

## 总结

`client.py` 文件是应用与外部LLM服务通信的入口点。通过预先配置好这些客户端实例，应用的其他部分（如 `LLMService`）就可以直接导入并使用它们，而无需关心底层的URL和认证细节。

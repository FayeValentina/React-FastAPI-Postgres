# 在本项目引入 RAG（检索增强生成）实施指南

> 目标：在已通过 `LLM_LOCAL_MODEL_GUIDE.md` 部署的本地大模型基础上，为后端服务增加检索增强生成能力，使 LLM 能够结合 PostgreSQL 中的私有知识库回答问题。

---

## 1) 架构与数据流

- **组件**：现有 `frontend`、`backend`、`postgres`、`llama_server`，新增的所有逻辑均封装在 `backend` 内部。
- **知识库**：利用 PostgreSQL + pgvector 扩展保存文本块与其向量表示。
- **调用链**：
  1. 离线：文件或文本 → 分块 → 向量化 → 写入 `knowledge_chunks` 表。
  2. 在线：用户问题 → 向量化 → PostgreSQL 相似度检索 → 构造增强 Prompt → 调用 `llama_server` → 返回答案。
- **对前端与 llama_server 透明**：前端仍通过 WebSocket 与后端通信，后端再决定是否携带检索到的上下文。

---

## 2) 依赖与环境变量

### 后端依赖
在 `backend/pyproject.toml` 的 `[tool.poetry.dependencies]` 中新增：

```toml
sentence-transformers = "^3.0.1"
pgvector = "^0.2.5"
nltk = "^3.9"
```

然后在 `backend` 目录执行：

```bash
# 生成新的 lock 文件并安装
poetry lock
poetry install
# 下载分词器数据（首次执行即可）
poetry run python -m nltk.downloader punkt
```

若在容器中开发，可使用：

```bash
docker compose exec backend poetry lock && \
docker compose exec backend poetry install && \
docker compose exec backend poetry run python -m nltk.downloader punkt
```

### 环境变量
在 `.env.dev` 与 `.env.prod` 中新增：

```bash
# 向量模型名称（SentenceTransformers Hub 上的模型）
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
# 检索返回的上下文块数量
RAG_TOP_K=3
```

`EMBEDDING_MODEL` 可按需替换为其他模型，但需与下文数据库表中的向量维度一致（此模型为 384 维）。

---

## 3) docker-compose 变更

### PostgreSQL 替换为 pgvector 镜像
在 `docker-compose.dev.yml` 与 `docker-compose.prod.yml` 中，将 `postgres` 服务的镜像改为：

```yaml
postgres:
  image: pgvector/pgvector:pg17
  # 其余配置保持不变
```

`pgvector/pgvector` 镜像已预装 `pgvector` 扩展，无需手动编译。

### 后端环境变量透传
在 `backend` 服务的 `environment` 中补充：

```yaml
- EMBEDDING_MODEL=${EMBEDDING_MODEL}
- RAG_TOP_K=${RAG_TOP_K:-3}
```

修改完成后执行 `docker compose up -d --build` 以拉取新镜像并重建服务。

---

## 4) 数据库迁移：构建知识库表

1. **生成迁移文件**

```bash
docker compose exec backend alembic revision -m "add knowledge table" --autogenerate
```

2. **编辑迁移文件**（示例路径：`backend/alembic/versions/xxxxxxxx_add_knowledge_table.py`）：

```python
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = 'xxxx'
down_revision = 'prev'


def upgrade() -> None:
    # 启用 pgvector 扩展
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 知识块表
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('source', sa.String, nullable=True, comment='来源标识'),
        sa.Column('content', sa.Text, nullable=False, comment='文本内容'),
        sa.Column('embedding', Vector(dim=384), nullable=False, comment='向量表示'),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('now()')),
    )

    # 向量索引（IVFFlat）
    op.create_index(
        'ix_knowledge_chunks_embedding',
        'knowledge_chunks',
        ['embedding'],
        postgresql_using='ivfflat',
        postgresql_with={'lists': 100},
    )


def downgrade() -> None:
    op.drop_index('ix_knowledge_chunks_embedding', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
    op.execute("DROP EXTENSION IF EXISTS vector;")
```

3. **运行迁移**

```bash
docker compose exec backend alembic upgrade head
```

---

## 5) 文本分块与向量化策略

- **分块**：
  - 先用 `nltk.sent_tokenize` 按句切分。
  - 逐句累加成每块约 300 个字符，块与块之间保留 50 字符重叠，避免语义断裂。
- **向量化**：
  - 使用 `SentenceTransformer(EMBEDDING_MODEL)`。
  - 调用 `encode(chunks, normalize_embeddings=True)` 得到 384 维向量。
- **存储**：每个块作为一行写入 `knowledge_chunks`，并记录 `source`（如文件名、URL）。

该流程可封装在 `app/modules/knowledge_base/service.py` 中，例如：

```python
from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from . import models

model = SentenceTransformer(settings.EMBEDDING_MODEL)

async def add_document_to_knowledge_base(db: AsyncSession, doc: schemas.DocumentCreate) -> int:
    chunks = split_text(doc.content)          # 分块
    vectors = model.encode(chunks, normalize_embeddings=True)
    for content, embedding in zip(chunks, vectors):
        db.add(models.KnowledgeChunk(source=doc.source, content=content, embedding=embedding))
    await db.commit()
    return len(chunks)
```

`split_text` 为自定义的分块函数，实现上述策略即可。

---

## 6) 检索与 API 集成

### 6.1 搜索相似文本
在同一 `service.py` 中实现：

```python
from sqlalchemy import select

async def search_similar_chunks(db: AsyncSession, query: str, top_k: int) -> list[models.KnowledgeChunk]:
    q_emb = model.encode([query], normalize_embeddings=True)[0]
    stmt = (
        select(models.KnowledgeChunk)
        .order_by(models.KnowledgeChunk.embedding.cosine_distance(q_emb))
        .limit(top_k)
    )
    result = await db.scalars(stmt)
    return result.all()
```

（`cosine_distance` 为 pgvector 提供的运算符，SQLAlchemy 0.2.5 起支持。）

可选：同时使用 PostgreSQL `tsvector` 建立全文索引，在向量得分接近时结合 `to_tsquery` 做关键词过滤，提升准确率。

### 6.2 文档入库 API

新建 `app/modules/knowledge_base/schemas.py`：

```python
from pydantic import BaseModel

class DocumentCreate(BaseModel):
    source: str
    content: str
```

在 `app/api/v1/endpoints/knowledge.py` 中编写路由：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.postgres_base import get_async_session
from app.modules.knowledge_base import service, schemas

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

@router.post("/add-document", status_code=201)
async def add_document(doc: schemas.DocumentCreate, db: AsyncSession = Depends(get_async_session)):
    count = await service.add_document_to_knowledge_base(db, doc)
    return {"message": f"文档已添加并切分为 {count} 块"}
```

别忘在 `app/api/v1/router.py` 中 `include_router`。

---

## 7) WebSocket 聊天整合 RAG

在现有 `app/api/v1/endpoints/llm_ws.py` 中：

1. 注入数据库依赖与检索函数。
2. 在收到用户消息后：
   - 调用 `search_similar_chunks` 获取 `top_k` 块上下文。
   - 将这些内容拼接为 `context_str`，与用户问题一起组装成增强 Prompt。
   - 以低 `temperature`（如 0.1）调用 `llama_server`，并保持原有流式返回逻辑。

简化示例：

```python
similar = await search_similar_chunks(db, user_text, settings.RAG_TOP_K)
context = "\n---\n".join(c.content for c in similar)
aug_prompt = f"请参考以下资料回答问题，如果资料不足请说明：\n{context}\n问题：{user_text}"
```

---

## 8) 运行与验证

1. 按前述步骤更新依赖、环境变量、Compose 与数据库迁移。
2. 重新启动服务：`docker compose up -d --build`。
3. 向知识库添加文档：
   
   ```bash
   curl -X POST http://localhost/api/v1/knowledge/add-document \
     -H "Content-Type: application/json" \
     -d '{"source":"README","content":"...任意文本..."}'
   ```
4. 打开前端聊天页面：
   - 提出与文档相关的问题 → 模型应给出基于上下文的回答。
   - 提出无关问题 → 模型应提示“资料不足”。

---

## 9) 后续优化

- **更智能的分块**：可引入 `langchain` 的 `RecursiveCharacterTextSplitter` 或基于 Token 的分块策略。
- **混合检索**：结合向量相似度与 `tsvector`/关键词搜索，提高召回率。
- **批量/异步入库**：利用现有 `taskiq` 任务队列，将文档预处理放到后台执行。
- **答案出处展示**：在前端将命中的 `source` 返回给用户，增强可解释性。

---

按本文档操作即可在项目中实现一个可直接参考的 RAG 系统，与本地大模型协同工作。

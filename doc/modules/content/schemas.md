# `schemas.py` (content) 文档

此文件定义了与抓取的Reddit内容相关的Pydantic模型，用于API的数据验证和响应格式化。

## `RedditPostResponse(RedditPostBase)`
- **用途**: 作为API响应返回单个Reddit帖子信息的模型。
- **继承**: 继承自 `RedditPostBase`，包含了帖子的所有核心字段。
- **扩展字段**: 
    - `id: str`: 帖子的唯一ID。
    - `scraped_at: datetime`: 内容被抓取的时间。
- **配置**: `model_config = ConfigDict(from_attributes=True)` 允许该模型直接从 `RedditPost` ORM实例创建。
- **注册**: 被 `@register_pydantic_model` 装饰，以便可以被缓存系统处理。

## `RedditCommentResponse(RedditCommentBase)`
- **用途**: 作为API响应返回单个Reddit评论信息的模型。
- **继承**: 继承自 `RedditCommentBase`，包含了评论的所有核心字段。
- **扩展字段**: 
    - `id: str`: 评论的唯一ID。
    - `post_id: str`: 所属帖子的ID。
    - `scraped_at: datetime`: 内容被抓取的时间。
- **配置**: 同样配置为可以从 `RedditComment` ORM实例创建。
- **注册**: 被 `@register_pydantic_model` 装饰，以便可以被缓存系统处理。

## `RedditContentListResponse(BaseModel)`
- **用途**: 一个通用的列表响应模型，可以同时包含帖子列表和/或评论列表，并附带分页信息。
- **字段**:
    - `posts: Optional[List[RedditPostResponse]]`: 帖子数据列表。
    - `comments: Optional[List[RedditCommentResponse]]`: 评论数据列表。
    - `total_count: int`: 符合条件的总记录数。
    - `page: int`: 当前页码。
    - `page_size: int`: 每页大小。

## `CommentSearchRequest(BaseModel)`
- **用途**: 作为评论搜索API的请求体验证模型。
- **字段**: 定义了搜索所需的所有参数，并使用 `Field` 进行了验证：
    - `query: str`: 搜索关键词，最小长度为1。
    - `subreddits: Optional[List[str]]`: 可选的子版块列表。
    - `min_score: int`: 最小得分，默认为0。
    - `days: Optional[int]`: 时间范围（天数），必须大于等于1。
    - `limit: int`: 返回结果数量，限制在1到500之间。

## `SubredditStats(BaseModel)`
- **用途**: 作为获取子版块统计信息API的响应模型。
- **字段**: 严格定义了 `get_subreddit_stats` 仓库方法返回的统计报告的结构，包括 `subreddit` 名称、时间周期、帖子统计、评论统计和热门作者列表。

## `RedditConnectionTestResponse(BaseModel)`
- **用途**: 用于测试与Reddit API连接状态的API的响应模型。
- **字段**:
    - `status: str`: 连接状态（例如 `"ok"` 或 `"error"`）。
    - `message: str`: 描述连接状态的详细信息。
    - `test_subreddit: Optional[str]`: 如果测试成功，返回用于测试的子版块名称。

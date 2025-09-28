# `content.py` (endpoints) 文档

此文件定义了与浏览和搜索已抓取的Reddit内容相关的API端点。所有端点都需要用户经过身份验证后才能访问。

## Router 配置
- **`prefix`**: `/content`
- **`tags`**: `["content"]`
- **依赖**: 所有端点都依赖于 `get_current_active_user`，确保只有已登录的活跃用户才能访问。

## Endpoints

### `GET /posts/{post_id}/comments`
- **功能**: 获取指定帖子的评论列表。
- **路径参数**: `post_id: str` - 要查询的Reddit帖子的ID。
- **查询参数**: `limit: int` - 返回评论的最大数量，默认为100。
- **响应模型**: `List[RedditCommentResponse]`
- **逻辑**: 调用 `CRUDRedditContent.get_comments_by_post` 方法，从数据库中检索与 `post_id` 关联的、按得分排序的评论列表。如果找不到帖子或评论，则返回404错误。

### `POST /comments/search`
- **功能**: 根据多种条件搜索评论。
- **请求体**: `CommentSearchRequest` - 包含以下字段：
    - `query`: 搜索关键词。
    - `subreddits` (可选): 要限定的子版块列表。
    - `min_score` (可选): 评论的最小得分。
    - `days` (可选): 搜索最近N天内抓取的数据。
    - `limit`: 返回结果的最大数量。
- **响应模型**: `List[RedditCommentResponse]`
- **逻辑**: 将请求体中的所有参数传递给 `CRUDRedditContent.search_comments` 方法，执行数据库查询并返回匹配的评论列表。

### `GET /subreddits/{subreddit}/stats`
- **功能**: 获取指定子版块（subreddit）在特定时间段内的统计信息。
- **路径参数**: `subreddit: str` - 要查询的子版块名称。
- **查询参数**: `days: int` - 统计的时间范围（天数），默认为30天。
- **响应模型**: `SubredditStats`
- **逻辑**: 调用 `CRUDRedditContent.get_subreddit_stats` 方法，该方法会执行多个聚合查询来计算帖子和评论的总数、平均分、热门作者等信息，并以结构化的 `SubredditStats` 对象返回。

--- 
*注意：该文件中的 `GET /posts` 和 `GET /comments` 端点似乎引用了不存在的仓库方法，并且其权限逻辑与当前模型不符，因此在本文档中未详细描述其预期行为。*

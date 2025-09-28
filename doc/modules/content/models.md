# `models.py` (content) 文档

此文件定义了与内容抓取相关的SQLAlchemy ORM模型，主要用于存储从Reddit抓取的数据，包括帖子（Posts）和评论（Comments）。

## `RedditPost(Base)` 模型

这个类代表了从Reddit抓取的一篇帖子，映射到 `reddit_posts` 表。

### 主要字段
- **`id: Mapped[str]`**: 主键，直接使用Reddit帖子的唯一ID（例如 `"t3_123abc"`），而不是自增整数。这可以有效防止重复抓取和存储同一篇帖子。

- **帖子基本信息**:
    - `title`: 帖子标题。
    - `author`: 作者用户名。
    - `subreddit`: 帖子所在的子版块名称。
    - `subreddit_subscribers`: 该子版块的订阅人数。

- **内容**:
    - `content`: 帖子的正文内容（仅限自发帖，即 `is_self=True` 的帖子）。
    - `url`: 帖子的链接。对于链接类型的帖子，这是指向外部网站的URL；对于自发帖，这是帖子的永久链接。
    - `domain`: 帖子链接的域名（例如 `i.redd.it`, `youtube.com`）。

- **统计数据**:
    - `score`: 帖子的得分（顶 - 踩）。
    - `upvote_ratio`: 顶帖率。
    - `num_comments`: 评论数量。

- **分类和标签**:
    - `flair_text`: 帖子的“Flair”，一种由子版块管理员设置的分类标签。
    - `is_self`: 是否为自发帖（纯文本帖子）。
    - `is_nsfw`: 是否为“不宜在工作场所观看”（Not Safe For Work）的内容。
    - `is_spoiler`: 是否包含剧透。

- **时间信息**:
    - `reddit_created_at`: 帖子在Reddit上原始的创建时间。
    - `scraped_at`: 本地系统抓取并存入数据库的时间。

### 关联关系
- `comments: Mapped[List["RedditComment"]]`: 定义了与 `RedditComment` 模型的一对多关系。当一个帖子被删除时，所有与之关联的评论也会被级联删除 (`cascade="all, delete-orphan"`)。

## `RedditComment(Base)` 模型

这个类代表了从Reddit抓取的一条评论，映射到 `reddit_comments` 表。

### 主要字段
- **`id: Mapped[str]`**: 主键，同样使用Reddit评论的唯一ID。
- **`post_id: Mapped[str]`**: 外键，关联到 `reddit_posts` 表，指明这条评论属于哪篇帖子。设置了 `ondelete="CASCADE"`，确保在帖子被删除时，数据库层面会自动删除其下的所有评论。

- **评论基本信息**:
    - `author`: 评论作者。
    - `body`: 评论内容。
    - `subreddit`: 评论所在的子版块。

- **评论层级**:
    - `parent_id`: 父评论的ID。用于构建评论的树状层级结构。
    - `depth`: 评论的深度（0代表顶层评论）。
    - `is_submitter`: 评论作者是否就是原帖的作者。

- **统计数据**:
    - `score`: 评论的得分。
    - `controversiality`: 评论的争议性指数。

- **时间信息**:
    - `reddit_created_at`: 评论在Reddit上的原始创建时间。
    - `scraped_at`: 本地系统抓取的时间。

### 关联关系
- `post: Mapped["RedditPost"]`: 定义了与 `RedditPost` 模型的多对一关系，方便从评论对象直接访问其所属的帖子对象。

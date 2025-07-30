## 1. **reddit_scraper_service.py** - 可以合并的方法

### 删除不必要的包装方法：

```python
# 🔴 可以删除这两个semaphore包装方法
async def _scrape_subreddit_with_semaphore(self, semaphore, config):
    """可以删除 - 直接在调用处使用semaphore"""
    
async def _scrape_post_comments_with_semaphore(self, semaphore, post_id, limit, subreddit_name):
    """可以删除 - 直接在调用处使用semaphore"""
```

### 优化后的代码：
```python
# ✅ 直接在主方法中使用semaphore
async def scrape_multiple_subreddits_concurrent(self, subreddit_configs):
    semaphore = asyncio.Semaphore(5)
    
    async def scrape_with_semaphore(config):
        async with semaphore:
            return await self.scrape_posts_with_details(
                subreddit_name=config['name'],
                limit=config.get('limit', 50),
                # ... 其他参数
            )
    
    tasks = [scrape_with_semaphore(config) for config in subreddit_configs]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```

## 2. **scraping_orchestrator.py** - 重复方法合并

### 🔴 删除重复的执行方法：

```python
# 这两个方法功能重复，可以合并为一个
async def execute_scraping_session(self, db, bot_config_id, session_type='manual')
async def execute_scraping_session_with_existing(self, db, session_id)
```

### ✅ 合并为统一方法：
```python
async def execute_scraping_session(
    self,
    db: AsyncSession,
    bot_config_id: Optional[int] = None,
    session_id: Optional[int] = None,
    session_type: str = 'manual'
) -> Optional[Dict[str, Any]]:
    """统一的爬取会话执行方法"""
    
    # 如果提供session_id，使用现有会话
    if session_id:
        session = await CRUDScrapeSession.get_session_by_id(db, session_id)
        if not session:
            return None
        bot_config_id = session.bot_config_id
    
    # 如果没有session_id但有bot_config_id，创建新会话
    elif bot_config_id:
        session = await self._create_new_session(db, bot_config_id, session_type)
    
    else:
        raise ValueError("必须提供 session_id 或 bot_config_id")
    
    # 统一的执行逻辑
    return await self._execute_session_core(db, session)
```

### 🔴 删除简单的包装方法：
```python
# 可以删除 - 功能太简单，直接内联到调用处
async def _analyze_comment_quality(self, db, session_id, bot_config):
    """只做了简单的长度和分数过滤，可以内联"""
```

### 🔴 简化不必要的方法：
```python
# 可以简化
async def get_active_configs_and_execute(self, db):
    """可以简化为一行调用"""
    # 原来的逻辑可以直接在调用处实现
```

## 3. **reddit_content.py** - 删除重复和无用方法

### 🔴 删除功能重复的方法：

```python
# 删除 - 功能与search_comments重复
async def get_top_comments_by_subreddit(self, db, subreddit, days=7, limit=50):
    """可以用search_comments替代"""

# 删除 - 用途不大，没有实际调用
async def get_content_by_score_range(self, db, min_score, max_score, content_type, subreddits, limit):
    """用途不明确，可以删除"""
```

### ✅ 保留但需要被调用的方法：
```python
# 保留但需要添加定时调用
async def delete_old_content(self, db, days_to_keep=90):
    """有用但未被调用，需要添加定时任务"""
```

## 4. **scrape_session.py** - 优化查询方法

### 🔴 可以合并的查询方法：

```python
# 这些方法有相似的查询逻辑，可以合并
async def get_sessions_by_config(self, db, bot_config_id, limit=50, status=None, session_type=None)
async def get_sessions_by_user(self, db, user_id, limit=50, status=None, session_type=None)
```

### ✅ 合并为通用查询方法：
```python
async def get_sessions(
    self,
    db: AsyncSession,
    bot_config_id: Optional[int] = None,
    user_id: Optional[int] = None,
    limit: int = 50,
    status: Optional[str] = None,
    session_type: Optional[str] = None
) -> List[ScrapeSession]:
    """通用的会话查询方法"""
    
    query = select(ScrapeSession)
    
    if bot_config_id:
        query = query.where(ScrapeSession.bot_config_id == bot_config_id)
    elif user_id:
        # 先获取用户的配置IDs
        config_result = await db.execute(
            select(BotConfig.id).where(BotConfig.user_id == user_id)
        )
        config_ids = [row[0] for row in config_result.all()]
        if config_ids:
            query = query.where(ScrapeSession.bot_config_id.in_(config_ids))
        else:
            return []
    
    if status:
        query = query.where(ScrapeSession.status == status)
    if session_type:
        query = query.where(ScrapeSession.session_type == session_type)
    
    query = query.order_by(ScrapeSession.created_at.desc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
```

## 5. **bot_config.py** - 删除复杂的查询方法

### 🔴 删除复杂且用途不大的方法：

```python
# 删除 - 功能复杂但用途不大
async def get_config_with_recent_sessions(self, db, config_id, limit=10):
    """可以通过分别调用两个简单方法替代"""
```

### ✅ 替代方案：
```python
# 在需要的地方直接组合调用
bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
recent_sessions = await CRUDScrapeSession.get_sessions(db, bot_config_id=config_id, limit=10)
```

## 6. **跨文件的重复逻辑 - 权限检查**

### 🔴 提取重复的权限检查逻辑：

在多个路由中都有相同的权限检查：
```python
# 在多个地方重复出现
bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
if bot_config.user_id != current_user.id and not current_user.is_superuser:
    raise InsufficientPermissionsError("没有权限")
```

### ✅ 提取为公共方法：
```python
# backend/app/utils/permissions.py
async def check_bot_config_permission(
    db: AsyncSession, 
    config_id: int, 
    user: User
) -> BotConfig:
    """检查用户对Bot配置的权限"""
    bot_config = await CRUDBotConfig.get_bot_config_by_id(db, config_id)
    if not bot_config:
        raise HTTPException(status_code=404, detail="Bot配置不存在")
    
    if bot_config.user_id != user.id and not user.is_superuser:
        raise InsufficientPermissionsError("没有权限操作此配置")
    
    return bot_config
```

## 总结优化方案

### 可以删除的方法（8个）：
1. `RedditScraperService._scrape_subreddit_with_semaphore()`
2. `RedditScraperService._scrape_post_comments_with_semaphore()`
3. `ScrapingOrchestrator.execute_scraping_session_with_existing()` 
4. `ScrapingOrchestrator._analyze_comment_quality()`
5. `CRUDRedditContent.get_top_comments_by_subreddit()`
6. `CRUDRedditContent.get_content_by_score_range()`
7. `CRUDBotConfig.get_config_with_recent_sessions()`
8. `ScrapingOrchestrator.get_active_configs_and_execute()`

### 可以合并的方法（4组）：
1. 合并两个执行方法为一个统一的执行方法
2. 合并会话查询方法为通用查询方法
3. 合并semaphore包装逻辑到主方法中
4. 提取公共权限检查逻辑

### 需要激活使用的方法（2个）：
1. `CRUDRedditContent.delete_old_content()` - 添加定时清理任务
2. `CRUDScrapeSession.cleanup_old_sessions()` - 添加定时清理任务

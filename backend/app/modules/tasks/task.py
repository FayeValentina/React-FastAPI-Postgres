"""
清理任务定义

参数定义规范（前端动态渲染用）：

1) 使用 typing.Annotated 给参数附加 UI 元信息（单一信息源由函数签名提供）
   - 语法：param: Annotated[T, {meta...}] = default
   - 示例：days_old: Annotated[int, {"ui_hint": "number", "min": 1}] = 7

2) 常用类型与渲染关系（注册表会输出 parameters[].type_info 与 parameters[].ui）
   - int/float → 数字输入（可用 min/max/step 约束）
   - bool → 开关/复选
   - str → 文本；名称以 email 结尾或 ui_hint="email" → 邮箱输入
   - dict/list/复杂嵌套/union → 建议 ui_hint="json"，前端以 JSON 文本域编辑
   - Optional[T] → 以 T 渲染，且非必填
   - Literal[...] / Enum → 自动 ui_hint="select"，choices 为枚举值列表

3) UI 元信息（可选字段，放在 Annotated 的字典中）
   - exclude_from_ui: bool         # 是否在前端隐藏该参数（不渲染、不提交）
   - ui_hint: str                  # 控件建议：select/number/text/email/boolean/json/password/textarea
   - choices: list                 # 下拉可选值（需配合 select 使用，或由 Literal/Enum 自动推断）
   - label: str                    # 自定义显示标签
   - description: str              # 说明文本（tooltip/帮助）
   - placeholder: str              # 占位文本
   - min/max/step: number          # 数字输入限制
   - pattern: str                  # 文本输入正则模式

4) 需要隐藏的参数（统一约定）
   - config_id: Annotated[Optional[int], {"exclude_from_ui": True}] = None
   - context:   Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends()
     （包含 FastAPI Depends/TaskiqDepends/Dependency 的默认值也会自动隐藏）

5) 前端数据来源
   - 端点：GET /api/v1/tasks/system/task-info（每个参数包含 name/type/type_info/default/required/kind/ui）
   - 注意：TypeInfo 仅包含 type/args（无 raw），前端主要依赖 ui 渲染
"""
from typing import Dict, Any, Optional, Annotated
import datetime
import logging

from taskiq import Context, TaskiqDepends
from app.broker import broker
from app.infrastructure.database.postgres_base import AsyncSessionLocal
from app.modules.auth.repository import crud_password_reset
from app.modules.content.repository import crud_reddit_content
from app.modules.tasks.repository import crud_task_execution
from app.infrastructure.auth.auth_service import auth_redis_service
from app.infrastructure.tasks.exec_record_decorators import execution_handler
from app.infrastructure.tasks.task_registry_decorators import task
from app.infrastructure.utils.common import get_current_time
from sqlalchemy import select, func
from app.modules.tasks.models import TaskExecution

logger = logging.getLogger(__name__)


@task("CLEANUP_TOKENS", queue="cleanup")
@broker.task(
    task_name="cleanup_expired_tokens",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
@execution_handler
async def cleanup_expired_tokens(
    config_id: Annotated[Optional[int], {"exclude_from_ui": True}] = None,  # 前端隐藏（后端自动注入/查询用）
    days_old: Annotated[
        int,
        {
            "exclude_from_ui": False,
            "ui_hint": "number",
            "choices": [1, 7, 30, 90],
            "label": "过期天数",
            "description": "清理多少天前的过期令牌（最小 1 天，默认 7 天）",
            "placeholder": "如 7",
            "min": 1,
            "max": 365,
            "step": 1,
            "pattern": "^[0-9]+$",
            "example": 7,
        },
    ] = 7,      # 数字输入，至少为 1
    context: Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends(),  # 前端隐藏（依赖注入）
) -> Dict[str, Any]:
    """
    清理过期的令牌
    """
    logger.info(f"开始清理 {days_old} 天前的过期令牌... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        expired_reset = await crud_password_reset.cleanup_expired(db, days_old=days_old)
        
        result = {
            "config_id": config_id,
            "expired_reset_tokens": expired_reset,
            "days_old": days_old
        }
        
        logger.info(f"清理过期令牌完成: {result}")
        return result


@task("CLEANUP_CONTENT", queue="cleanup")
@broker.task(
    task_name="cleanup_old_content",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
@execution_handler
async def cleanup_old_content(
    config_id: Annotated[Optional[int], {"exclude_from_ui": True}] = None,  # 前端隐藏（后端自动注入/查询用）
    days_old: Annotated[
        int,
        {
            "exclude_from_ui": False,
            "ui_hint": "number",
            "choices": [30, 90, 180, 365],
            "label": "内容保留天数",
            "description": "清理多少天前的旧内容（最小 1 天，默认 90 天）",
            "placeholder": "如 90",
            "min": 1,
            "max": 3650,
            "step": 1,
            "pattern": "^[0-9]+$",
            "example": 90,
        },
    ] = 90,     # 数字输入，至少为 1
    context: Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends(),  # 前端隐藏（依赖注入）
) -> Dict[str, Any]:
    """
    清理旧内容
    """
    logger.info(f"开始清理 {days_old} 天前的旧内容... (Config ID: {config_id})")
    
    async with AsyncSessionLocal() as db:
        deleted_posts, deleted_comments = await crud_reddit_content.delete_old_content(
            db, days_to_keep=days_old
        )
        
        result = {
            "config_id": config_id,
            "deleted_posts": deleted_posts,
            "deleted_comments": deleted_comments,
            "total_deleted": deleted_posts + deleted_comments,
            "days_old": days_old
        }
        
        logger.info(f"清理旧内容完成: {result}")
        return result


@task("CLEANUP_EXECUTIONS", queue="cleanup")
@broker.task(
    task_name="cleanup_old_executions",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
@execution_handler
async def cleanup_old_executions_task(
    config_id: Annotated[Optional[int], {"exclude_from_ui": True}] = None,  # 前端隐藏（与执行记录无强绑定，仅为统一参数）
    days_to_keep: Annotated[
        int,
        {
            "ui_hint": "number",
            "label": "保留天数",
            "description": "删除早于该天数的执行记录（默认 90 天）",
            "placeholder": "如 90",
            "min": 30,
            "max": 3650,
            "step": 1,
            "choices": [30, 60, 90, 180, 365],
            "example": 90,
            "pattern": "^[0-9]+$",
        },
    ] = 90,
    dry_run: Annotated[
        bool,
        {
            "ui_hint": "boolean",
            "label": "试运行(不执行删除)",
            "description": "仅统计将要删除的记录数量，不执行实际删除",
            "example": False,
        },
    ] = False,
    context: Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends(),  # 前端隐藏（依赖注入）
) -> Dict[str, Any]:
    """清理旧的执行记录（支持 dry-run 统计）。"""
    logger.info(f"开始清理旧执行记录... 保留天数: {days_to_keep}, dry_run={dry_run}")

    async with AsyncSessionLocal() as db:
        cutoff = get_current_time() - datetime.timedelta(days=days_to_keep)

        if dry_run:
            # 仅统计将要删除的数量
            result = await db.execute(
                select(func.count(TaskExecution.id)).where(TaskExecution.created_at < cutoff)
            )
            would_delete = int(result.scalar() or 0)
            summary = {
                "config_id": config_id,
                "days_to_keep": days_to_keep,
                "dry_run": True,
                "cutoff": cutoff.isoformat(),
                "would_delete_count": would_delete,
                "timestamp": get_current_time().isoformat(),
            }
            logger.info(f"执行记录清理试运行: {summary}")
            return summary

        # 实际删除
        deleted = await crud_task_execution.cleanup_old_executions(db, days_to_keep=days_to_keep)
        summary = {
            "config_id": config_id,
            "days_to_keep": days_to_keep,
            "dry_run": False,
            "cutoff": cutoff.isoformat(),
            "deleted_count": int(deleted or 0),
            "timestamp": get_current_time().isoformat(),
        }
        logger.info(f"执行记录清理完成: {summary}")
        return summary


@task("CLEANUP_AUTH_TOKENS", queue="cleanup")
@broker.task(
    task_name="cleanup_expired_auth_tokens",
    queue="cleanup",
    retry_on_error=True,
    max_retries=3,
)
@execution_handler
async def cleanup_expired_auth_tokens(
    config_id: Annotated[Optional[int], {"exclude_from_ui": True}] = None,
    context: Annotated[Context, {"exclude_from_ui": True}] = TaskiqDepends(),
) -> Dict[str, Any]:
    """清理过期的认证刷新令牌（Redis）。"""
    logger.info("开始清理过期的认证刷新令牌...")
    count = await auth_redis_service.cleanup_expired_tokens()
    result = {
        "config_id": config_id,
        "expired_token_deleted": int(count or 0),
        "timestamp": get_current_time().isoformat(),
    }
    logger.info(f"清理过期认证令牌完成: {result}")
    return result

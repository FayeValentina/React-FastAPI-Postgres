"""
测试超时任务定义
"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from taskiq import Context, TaskiqDepends
from app.broker import broker
from app.core.task_decorators import with_timeout_handling
from app.constant.task_registry import task

logger = logging.getLogger(__name__)


@task("TEST_TIMEOUT", queue="test")
@broker.task(
    task_name="test_timeout_task",
    queue="test",
    retry_on_error=True,
    max_retries=1,
)
@with_timeout_handling
async def test_timeout_task(
    config_id: Optional[int] = None,
    sleep_seconds: int = 30,
    context: Context = TaskiqDepends(),
    **kwargs
) -> Dict[str, Any]:
    """
    测试任务超时功能的任务
    
    Args:
        config_id: 任务配置ID
        sleep_seconds: 睡眠时间（秒）
        **kwargs: 额外参数
    
    Returns:
        任务执行结果
    """
    logger.info(f"测试任务开始，将睡眠 {sleep_seconds} 秒... (Config ID: {config_id})")
    
    # 模拟长时间运行的任务
    await asyncio.sleep(sleep_seconds)
    
    result = {
        "config_id": config_id,
        "sleep_seconds": sleep_seconds,
        "status": "completed",
        "message": f"任务成功完成，睡眠了 {sleep_seconds} 秒",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.info(f"测试任务完成: {result}")
    return result


@task("TEST_FAILURE", queue="test")
@broker.task(
    task_name="test_failure_task",
    queue="test",
    retry_on_error=False,
    max_retries=0,
)
@with_timeout_handling
async def test_failure_task(
    config_id: Optional[int] = None,
    error_type: str = "general",
    context: Context = TaskiqDepends(),
    **kwargs
) -> Dict[str, Any]:
    """
    测试任务失败的任务
    
    Args:
        config_id: 任务配置ID
        error_type: 错误类型 (general, value_error, type_error)
        **kwargs: 额外参数
    
    Returns:
        任务执行结果
    """
    logger.info(f"测试失败任务开始，将抛出 {error_type} 错误... (Config ID: {config_id})")
    
    # 故意抛出不同类型的异常
    if error_type == "value_error":
        raise ValueError("这是一个故意的ValueError测试")
    elif error_type == "type_error":
        raise TypeError("这是一个故意的TypeError测试")
    elif error_type == "zero_division":
        result = 1 / 0  # 故意除零错误
    else:
        raise Exception("这是一个故意的通用异常测试")
    
    # 这行不会被执行到
    return {"status": "should_not_reach_here"}


@task("TEST_SHORT_TIMEOUT", queue="test")
@broker.task(
    task_name="test_short_timeout_task",
    queue="test",
    retry_on_error=False,
    max_retries=0,
)
@with_timeout_handling
async def test_short_timeout_task(
    config_id: Optional[int] = None,
    sleep_seconds: int = 5,
    context: Context = TaskiqDepends(),
    **kwargs
) -> Dict[str, Any]:
    """
    测试短超时的任务（用于确保超时能被捕获）
    
    Args:
        config_id: 任务配置ID  
        sleep_seconds: 睡眠时间（秒）
        **kwargs: 额外参数
    
    Returns:
        任务执行结果
    """
    logger.info(f"短超时测试任务开始，将睡眠 {sleep_seconds} 秒... (Config ID: {config_id})")
    
    # 这个任务会运行较长时间，预期会被TaskIQ超时机制终止
    await asyncio.sleep(sleep_seconds)
    
    result = {
        "config_id": config_id,
        "sleep_seconds": sleep_seconds,
        "status": "completed",
        "message": f"短超时任务成功完成，睡眠了 {sleep_seconds} 秒",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.info(f"短超时测试任务完成: {result}")
    return result
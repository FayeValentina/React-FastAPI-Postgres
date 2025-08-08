#!/usr/bin/env python3
"""
测试tasks_manager功能的独立脚本
不依赖数据库，仅测试核心调度功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class MockDatabase:
    """模拟数据库操作"""
    def __init__(self):
        self.task_configs = {}
        self.next_id = 1
    
    async def create_task_config(self, config_data: Dict[str, Any]) -> int:
        """创建任务配置"""
        config_id = self.next_id
        self.next_id += 1
        
        self.task_configs[config_id] = {
            'id': config_id,
            'name': config_data['name'],
            'task_type': config_data['task_type'],
            'status': 'active',
            'task_params': config_data.get('task_params', {}),
            'schedule_config': config_data.get('schedule_config', {}),
            'created_at': datetime.utcnow()
        }
        
        logger.info(f"Mock: 创建任务配置 {config_id} - {config_data['name']}")
        return config_id
    
    async def get_task_config(self, config_id: int) -> Dict[str, Any]:
        """获取任务配置"""
        config = self.task_configs.get(config_id)
        if config:
            logger.info(f"Mock: 获取任务配置 {config_id}")
        return config
    
    async def get_active_configs(self):
        """获取活跃的任务配置"""
        active_configs = [
            config for config in self.task_configs.values()
            if config['status'] == 'active'
        ]
        logger.info(f"Mock: 获取 {len(active_configs)} 个活跃配置")
        return active_configs


# 模拟执行函数
async def mock_task_execution(task_config_id: int):
    """模拟任务执行"""
    logger.info(f"Mock: 执行任务配置 {task_config_id}")
    await asyncio.sleep(1)  # 模拟任务执行时间
    return f"任务 {task_config_id} 执行完成"


async def test_task_manager_basic_functions():
    """测试TaskManager的基本功能"""
    logger.info("=" * 50)
    logger.info("开始测试 TaskManager 基本功能")
    logger.info("=" * 50)
    
    # 由于TaskManager依赖数据库，我们需要先模拟其核心组件
    from app.core.scheduler import Scheduler
    from app.core.task_type import TaskType
    
    # 创建调度器
    scheduler = Scheduler()
    
    # 测试1: 启动调度器
    try:
        logger.info("测试1: 启动调度器")
        scheduler.start()
        logger.info("✓ 调度器启动成功")
    except Exception as e:
        logger.error(f"✗ 调度器启动失败: {e}")
        return
    
    # 测试2: 添加间隔任务
    try:
        logger.info("测试2: 添加间隔任务")
        job_id = scheduler.add_job(
            func=mock_task_execution,
            trigger_type='interval',
            job_id='test_interval_job',
            name='测试间隔任务',
            args=[1],
            seconds=5  # 每5秒执行一次
        )
        logger.info(f"✓ 间隔任务添加成功: {job_id}")
    except Exception as e:
        logger.error(f"✗ 间隔任务添加失败: {e}")
    
    # 测试3: 添加Cron任务
    try:
        logger.info("测试3: 添加Cron任务")
        job_id = scheduler.add_job(
            func=mock_task_execution,
            trigger_type='cron',
            job_id='test_cron_job',
            name='测试Cron任务',
            args=[2],
            minute='*',  # 每分钟执行
            second='30'  # 在30秒时执行
        )
        logger.info(f"✓ Cron任务添加成功: {job_id}")
    except Exception as e:
        logger.error(f"✗ Cron任务添加失败: {e}")
    
    # 测试4: 添加一次性任务
    try:
        logger.info("测试4: 添加一次性任务")
        run_time = datetime.now() + timedelta(seconds=10)
        job_id = scheduler.add_job(
            func=mock_task_execution,
            trigger_type='date',
            job_id='test_date_job',
            name='测试一次性任务',
            args=[3],
            run_date=run_time
        )
        logger.info(f"✓ 一次性任务添加成功: {job_id}，将在 {run_time} 执行")
    except Exception as e:
        logger.error(f"✗ 一次性任务添加失败: {e}")
    
    # 测试5: 查看所有任务
    try:
        logger.info("测试5: 查看所有任务")
        jobs = scheduler.get_all_jobs()
        logger.info(f"✓ 当前共有 {len(jobs)} 个任务:")
        for job in jobs:
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else '未安排'
            logger.info(f"  - {job.name} (ID: {job.id}, 下次运行: {next_run})")
    except Exception as e:
        logger.error(f"✗ 查看任务失败: {e}")
    
    # 运行一段时间观察调度器工作
    logger.info("测试6: 运行调度器 15 秒观察任务执行")
    try:
        await asyncio.sleep(15)
        logger.info("✓ 调度器运行观察完成")
    except Exception as e:
        logger.error(f"✗ 调度器运行出错: {e}")
    
    # 测试7: 暂停和恢复任务
    try:
        logger.info("测试7: 暂停和恢复任务")
        success = scheduler.pause_job('test_interval_job')
        if success:
            logger.info("✓ 暂停间隔任务成功")
            await asyncio.sleep(3)
            
            success = scheduler.resume_job('test_interval_job')
            if success:
                logger.info("✓ 恢复间隔任务成功")
            else:
                logger.error("✗ 恢复间隔任务失败")
        else:
            logger.error("✗ 暂停间隔任务失败")
    except Exception as e:
        logger.error(f"✗ 暂停/恢复任务出错: {e}")
    
    # 测试8: 移除任务
    try:
        logger.info("测试8: 移除任务")
        success = scheduler.remove_job('test_interval_job')
        if success:
            logger.info("✓ 移除间隔任务成功")
        else:
            logger.error("✗ 移除间隔任务失败")
            
        success = scheduler.remove_job('test_cron_job')
        if success:
            logger.info("✓ 移除Cron任务成功")
        else:
            logger.error("✗ 移除Cron任务失败")
    except Exception as e:
        logger.error(f"✗ 移除任务出错: {e}")
    
    # 关闭调度器
    try:
        logger.info("关闭调度器")
        scheduler.shutdown()
        logger.info("✓ 调度器关闭成功")
    except Exception as e:
        logger.error(f"✗ 调度器关闭失败: {e}")
    
    logger.info("=" * 50)
    logger.info("TaskManager 基本功能测试完成")
    logger.info("=" * 50)


async def test_task_dispatcher():
    """测试TaskDispatcher功能"""
    logger.info("=" * 50)
    logger.info("开始测试 TaskDispatcher 功能")
    logger.info("=" * 50)
    
    try:
        from app.core.task_dispatcher import TaskDispatcher
        from app.core.task_mapping import get_all_task_types, is_task_type_supported
        
        dispatcher = TaskDispatcher()
        
        # 测试1: 检查支持的任务类型
        logger.info("测试1: 检查支持的任务类型")
        task_types = dispatcher.get_supported_task_types()
        logger.info(f"✓ 支持的任务类型: {task_types}")
        
        # 测试2: 检查特定任务类型支持
        logger.info("测试2: 检查特定任务类型支持")
        for task_type in ['unknown_task']:
            supported = dispatcher.is_task_type_supported(task_type)
            status = "✓" if supported else "○"
            logger.info(f"{status} 任务类型 '{task_type}' 支持状态: {supported}")
        
        logger.info("✓ TaskDispatcher 功能测试完成")
        
    except Exception as e:
        logger.error(f"✗ TaskDispatcher 测试失败: {e}")
    
    logger.info("=" * 50)
    logger.info("TaskDispatcher 功能测试完成")
    logger.info("=" * 50)


async def main():
    """主测试函数"""
    logger.info("开始测试 tasks_manager 框架功能")
    
    # 测试基本调度器功能
    await test_task_manager_basic_functions()
    
    # 等待一段时间
    await asyncio.sleep(2)
    
    # 测试任务分发器功能
    await test_task_dispatcher()
    
    logger.info("所有测试完成!")


if __name__ == "__main__":
    asyncio.run(main())
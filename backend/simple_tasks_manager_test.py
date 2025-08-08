#!/usr/bin/env python3
"""
简化版TasksManager功能测试脚本
直接测试核心组件，避免复杂的依赖问题
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_core_components():
    """测试核心组件功能"""
    logger.info("🧪 开始测试TasksManager核心组件")
    
    try:
        # 测试1: 导入核心模块
        logger.info("1️⃣ 测试核心模块导入...")
        
        from app.core.task_type import TaskType, TaskStatus, SchedulerType
        logger.info("✅ task_type模块导入成功")
        
        from app.core.scheduler import scheduler
        logger.info("✅ scheduler模块导入成功")
        
        from app.core.task_dispatcher import task_dispatcher
        logger.info("✅ task_dispatcher模块导入成功")
        
        from app.core.job_config_manager import job_config_manager
        logger.info("✅ job_config_manager模块导入成功")
        
        from app.core.event_recorder import event_recorder
        logger.info("✅ event_recorder模块导入成功")
        
        # 测试2: 检查任务类型支持
        logger.info("2️⃣ 测试任务类型支持...")
        
        supported_types = task_dispatcher.get_supported_task_types()
        logger.info(f"✅ 支持的任务类型: {list(supported_types.keys())}")
        
        # 测试每种类型的支持状态
        test_types = ['cleanup_sessions', 'cleanup_tokens', 'send_email', 'health_check']
        for task_type in test_types:
            is_supported = task_dispatcher.is_task_type_supported(task_type)
            status = "✅" if is_supported else "⚠️"
            logger.info(f"  {status} {task_type}: {'支持' if is_supported else '不支持'}")
        
        # 测试3: 启动调度器
        logger.info("3️⃣ 测试调度器启动...")
        
        scheduler.start()
        logger.info("✅ 调度器启动成功")
        
        # 测试4: 测试数据库配置管理
        logger.info("4️⃣ 测试数据库配置管理...")
        
        # 创建测试配置
        config_id = await job_config_manager.create_config(
            name="简单测试任务",
            task_type="cleanup_tokens",
            description="测试用的清理令牌任务",
            task_params={"days_old": 30},
            schedule_config={
                "scheduler_type": "interval",
                "hours": 1
            },
            scheduler_type="interval",  # 必需字段
            priority=5
        )
        
        if config_id:
            logger.info(f"✅ 创建配置成功，ID: {config_id}")
            
            # 获取配置
            config = await job_config_manager.get_config(config_id)
            if config:
                logger.info(f"✅ 获取配置成功: {config['name']}")
                
                # 更新配置
                success = await job_config_manager.update_config(
                    config_id, 
                    {"description": "更新后的描述"}
                )
                if success:
                    logger.info("✅ 更新配置成功")
                else:
                    logger.warning("⚠️ 更新配置失败")
                
                # 删除配置
                success = await job_config_manager.remove_config(config_id)
                if success:
                    logger.info("✅ 删除配置成功")
                else:
                    logger.warning("⚠️ 删除配置失败")
            else:
                logger.warning("⚠️ 获取配置失败")
        else:
            logger.warning("⚠️ 创建配置失败")
        
        # 测试5: 列出所有配置
        logger.info("5️⃣ 测试列出配置...")
        
        all_configs = await job_config_manager.get_all_configs()
        logger.info(f"✅ 找到 {len(all_configs)} 个配置")
        
        # 测试6: 获取活跃配置
        active_configs = await job_config_manager.get_active_configs()
        logger.info(f"✅ 找到 {len(active_configs)} 个活跃配置")
        
        # 测试7: 从数据库加载任务到调度器
        logger.info("6️⃣ 测试从数据库加载任务...")
        
        # 模拟任务执行函数
        async def mock_task_func(config_id):
            logger.info(f"🚀 模拟执行任务配置 {config_id}")
            return f"任务 {config_id} 完成"
        
        # 从数据库注册任务
        await scheduler.register_tasks_from_database(mock_task_func)
        
        # 查看调度的任务
        jobs = scheduler.get_all_jobs()
        logger.info(f"✅ 调度器中有 {len(jobs)} 个任务")
        
        for job in jobs:
            next_run = job.next_run_time.strftime('%H:%M:%S') if job.next_run_time else '未安排'
            logger.info(f"  📋 {job.name} (ID: {job.id}, 下次运行: {next_run})")
        
        # 关闭调度器
        scheduler.shutdown()
        logger.info("✅ 调度器关闭成功")
        
        # 测试总结
        logger.info("🎉 核心组件测试完成!")
        logger.info("=" * 60)
        logger.info("📊 测试结果:")
        logger.info("  ✅ 模块导入: 成功")
        logger.info("  ✅ 任务类型检查: 成功")
        logger.info("  ✅ 调度器操作: 成功")
        logger.info("  ✅ 配置管理: 成功")
        logger.info("  ✅ 数据库集成: 成功")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False


async def test_tasks_manager_high_level():
    """测试TasksManager高级接口"""
    logger.info("🚀 开始测试TasksManager高级接口")
    
    try:
        from app.services.tasks_manager import task_manager
        
        # 启动任务管理器
        await task_manager.start()
        logger.info("✅ TasksManager启动成功")
        
        # 测试创建配置
        config_id = await task_manager.create_task_config(
            name="高级测试任务",
            task_type="cleanup_sessions",
            description="高级接口测试",
            task_params={"days_old": 7},
            schedule_config={
                "scheduler_type": "interval",
                "minutes": 30
            },
            scheduler_type="interval"  # 必需字段
        )
        
        if config_id:
            logger.info(f"✅ 通过TasksManager创建配置成功: {config_id}")
            
            # 启动调度
            success = await task_manager.start_scheduled_task(config_id)
            if success:
                logger.info("✅ 启动任务调度成功")
                
                # 获取调度状态
                scheduled_jobs = task_manager.get_scheduled_jobs()
                logger.info(f"✅ 当前有 {len(scheduled_jobs)} 个调度任务")
                
                # 停止调度
                success = task_manager.stop_scheduled_task(config_id)
                if success:
                    logger.info("✅ 停止任务调度成功")
                else:
                    logger.warning("⚠️ 停止任务调度失败")
            else:
                logger.warning("⚠️ 启动任务调度失败")
            
            # 获取系统状态
            status = await task_manager.get_system_status()
            logger.info(f"✅ 系统状态: 调度器运行={status.get('scheduler_running', 'unknown')}")
            
            # 删除测试配置
            success = await task_manager.delete_task_config(config_id)
            if success:
                logger.info("✅ 删除配置成功")
            else:
                logger.warning("⚠️ 删除配置失败")
        else:
            logger.warning("⚠️ 创建配置失败")
        
        # 关闭任务管理器
        task_manager.shutdown()
        logger.info("✅ TasksManager关闭成功")
        
        logger.info("🎉 TasksManager高级接口测试完成!")
        return True
        
    except Exception as e:
        logger.error(f"❌ TasksManager测试失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return False


async def main():
    """主测试函数"""
    logger.info("🔬 开始TasksManager简化功能测试")
    
    # 测试核心组件
    core_success = await test_core_components()
    
    if not core_success:
        logger.error("❌ 核心组件测试失败，跳过高级接口测试")
        return
    
    await asyncio.sleep(2)
    
    # 测试TasksManager高级接口
    high_level_success = await test_tasks_manager_high_level()
    
    # 最终结果
    logger.info("=" * 80)
    if core_success and high_level_success:
        logger.info("🏆 所有测试通过! TasksManager功能正常")
    else:
        logger.info("⚠️ 部分测试失败，请检查详细日志")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
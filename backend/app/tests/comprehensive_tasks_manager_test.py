#!/usr/bin/env python3
"""
TasksManager 完整功能测试脚本
测试所有的任务管理功能，包括配置管理、调度管理、批量操作、统计分析等
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class TasksManagerTester:
    """TasksManager功能测试类"""
    
    def __init__(self):
        self.task_manager = None
        self.test_results = {
            'config_management': {},
            'schedule_management': {},
            'batch_operations': {},
            'health_statistics': {},
            'system_management': {}
        }
        self.created_config_ids = []
    
    async def setup(self):
        """初始化测试环境"""
        logger.info("🔧 初始化测试环境...")
        
        try:
            from app.services.tasks_manager import task_manager
            self.task_manager = task_manager
            
            # 启动任务管理器
            await self.task_manager.start()
            logger.info("✅ TasksManager启动成功")
            
            return True
        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            return False
    
    async def cleanup(self):
        """清理测试环境"""
        logger.info("🧹 清理测试环境...")
        
        try:
            # 清理创建的测试配置
            for config_id in self.created_config_ids:
                try:
                    await self.task_manager.delete_task_config(config_id)
                    logger.info(f"🗑️ 清理测试配置: {config_id}")
                except Exception as e:
                    logger.warning(f"清理配置 {config_id} 失败: {e}")
            
            # 关闭任务管理器
            self.task_manager.shutdown()
            logger.info("✅ 清理完成")
            
        except Exception as e:
            logger.error(f"❌ 清理失败: {e}")
    
    def print_section_header(self, title: str):
        """打印测试章节标题"""
        logger.info("=" * 80)
        logger.info(f"🧪 {title}")
        logger.info("=" * 80)
    
    def print_test_result(self, test_name: str, success: bool, details: str = None):
        """打印测试结果"""
        status = "✅" if success else "❌"
        message = f"{status} {test_name}"
        if details:
            message += f" - {details}"
        logger.info(message)
        return success
    
    # ================== 任务配置管理功能测试 ==================
    
    async def test_config_management(self):
        """测试任务配置管理功能"""
        self.print_section_header("任务配置管理功能测试")
        results = {}
        
        # 测试1: 创建任务配置
        try:
            config_id = await self.task_manager.create_task_config(
                name="测试清理任务",
                task_type="cleanup_tokens",
                description="用于测试的清理任务",
                task_params={
                    "days_old": 7
                },
                schedule_config={
                    "scheduler_type": "interval",
                    "hours": 2
                },
                priority=8,
                max_instances=1,
                timeout_seconds=300,
                retry_count=3
            )
            
            if config_id:
                self.created_config_ids.append(config_id)
                results['create_config'] = self.print_test_result(
                    "创建任务配置",
                    True,
                    f"配置ID: {config_id}"
                )
            else:
                results['create_config'] = self.print_test_result(
                    "创建任务配置",
                    False,
                    "返回的配置ID为None"
                )
                
        except Exception as e:
            results['create_config'] = self.print_test_result(
                "创建任务配置",
                False,
                f"异常: {e}"
            )
        
        # 测试2: 获取任务配置
        if self.created_config_ids:
            try:
                config = await self.task_manager.get_task_config(self.created_config_ids[0])
                if config and config.get('name') == "测试清理任务":
                    results['get_config'] = self.print_test_result(
                        "获取任务配置",
                        True,
                        f"名称: {config.get('name')}, 类型: {config.get('task_type')}"
                    )
                else:
                    results['get_config'] = self.print_test_result(
                        "获取任务配置",
                        False,
                        "配置信息不正确"
                    )
            except Exception as e:
                results['get_config'] = self.print_test_result(
                    "获取任务配置",
                    False,
                    f"异常: {e}"
                )
        
        # 测试3: 创建多种类型的任务配置
        test_configs = [
            {
                "name": "测试清理令牌任务",
                "task_type": "cleanup_tokens",
                "description": "清理过期令牌",
                "task_params": {"days_old": 30},
                "schedule_config": {
                    "scheduler_type": "cron",
                    "minute": "0",
                    "hour": "2",
                    "day": "*",
                    "month": "*",
                    "day_of_week": "*"
                }
            },
            {
                "name": "测试邮件任务",
                "task_type": "send_email",
                "description": "发送邮件通知",
                "task_params": {
                    "recipient_emails": ["test@example.com"],
                    "subject": "测试邮件",
                    "template_name": "test_template"
                },
                "schedule_config": {
                    "scheduler_type": "date",
                    "run_date": (datetime.now() + timedelta(hours=1)).isoformat()
                }
            }
        ]
        
        create_multiple_success = True
        for config_data in test_configs:
            try:
                config_id = await self.task_manager.create_task_config(**config_data)
                if config_id:
                    self.created_config_ids.append(config_id)
                    logger.info(f"  ✓ 创建 {config_data['task_type']} 任务成功: {config_id}")
                else:
                    create_multiple_success = False
                    logger.error(f"  ✗ 创建 {config_data['task_type']} 任务失败")
            except Exception as e:
                create_multiple_success = False
                logger.error(f"  ✗ 创建 {config_data['task_type']} 任务异常: {e}")
        
        results['create_multiple_configs'] = self.print_test_result(
            "创建多种类型任务配置",
            create_multiple_success,
            f"共创建 {len(self.created_config_ids)} 个配置"
        )
        
        # 测试4: 更新任务配置
        if self.created_config_ids:
            try:
                success = await self.task_manager.update_task_config(
                    self.created_config_ids[0],
                    {"description": "更新后的描述", "priority": 9}
                )
                results['update_config'] = self.print_test_result(
                    "更新任务配置",
                    success
                )
            except Exception as e:
                results['update_config'] = self.print_test_result(
                    "更新任务配置",
                    False,
                    f"异常: {e}"
                )
        
        # 测试5: 列出任务配置
        try:
            configs = await self.task_manager.list_task_configs()
            results['list_configs'] = self.print_test_result(
                "列出所有任务配置",
                len(configs) >= len(self.created_config_ids),
                f"找到 {len(configs)} 个配置"
            )
        except Exception as e:
            results['list_configs'] = self.print_test_result(
                "列出所有任务配置",
                False,
                f"异常: {e}"
            )
        
        # 测试6: 按类型筛选任务配置
        try:
            cleanup_configs = await self.task_manager.list_task_configs(task_type="cleanup_tokens")
            results['filter_configs'] = self.print_test_result(
                "按类型筛选任务配置",
                len(cleanup_configs) >= 1,
                f"找到 {len(cleanup_configs)} 个cleanup_tokens配置"
            )
        except Exception as e:
            results['filter_configs'] = self.print_test_result(
                "按类型筛选任务配置",
                False,
                f"异常: {e}"
            )
        
        self.test_results['config_management'] = results
        return results
    
    # ================== 任务调度管理功能测试 ==================
    
    async def test_schedule_management(self):
        """测试任务调度管理功能"""
        self.print_section_header("任务调度管理功能测试")
        results = {}
        
        if not self.created_config_ids:
            logger.warning("⚠️ 没有可用的任务配置，跳过调度管理测试")
            return {}
        
        test_config_id = self.created_config_ids[0]
        
        # 测试1: 启动任务调度
        try:
            success = await self.task_manager.start_scheduled_task(test_config_id)
            results['start_schedule'] = self.print_test_result(
                "启动任务调度",
                success,
                f"配置ID: {test_config_id}"
            )
        except Exception as e:
            results['start_schedule'] = self.print_test_result(
                "启动任务调度",
                False,
                f"异常: {e}"
            )
        
        # 等待一下，确保调度器加载完成
        await asyncio.sleep(2)
        
        # 测试2: 查看调度中的任务
        try:
            scheduled_jobs = self.task_manager.get_scheduled_jobs()
            results['get_scheduled_jobs'] = self.print_test_result(
                "获取调度中的任务",
                len(scheduled_jobs) > 0,
                f"找到 {len(scheduled_jobs)} 个调度中的任务"
            )
            
            # 打印调度任务详情
            for job in scheduled_jobs:
                logger.info(f"  📋 任务: {job.get('name')} (ID: {job.get('job_id')}, 下次执行: {job.get('next_run_time')})")
                
        except Exception as e:
            results['get_scheduled_jobs'] = self.print_test_result(
                "获取调度中的任务",
                False,
                f"异常: {e}"
            )
        
        # 测试3: 暂停任务调度
        try:
            success = self.task_manager.pause_scheduled_task(test_config_id)
            results['pause_schedule'] = self.print_test_result(
                "暂停任务调度",
                success
            )
        except Exception as e:
            results['pause_schedule'] = self.print_test_result(
                "暂停任务调度",
                False,
                f"异常: {e}"
            )
        
        # 等待一下
        await asyncio.sleep(1)
        
        # 测试4: 恢复任务调度
        try:
            success = self.task_manager.resume_scheduled_task(test_config_id)
            results['resume_schedule'] = self.print_test_result(
                "恢复任务调度",
                success
            )
        except Exception as e:
            results['resume_schedule'] = self.print_test_result(
                "恢复任务调度",
                False,
                f"异常: {e}"
            )
        
        # 测试5: 重新加载任务调度
        try:
            success = await self.task_manager.reload_scheduled_task(test_config_id)
            results['reload_schedule'] = self.print_test_result(
                "重新加载任务调度",
                success
            )
        except Exception as e:
            results['reload_schedule'] = self.print_test_result(
                "重新加载任务调度",
                False,
                f"异常: {e}"
            )
        
        # 测试6: 停止任务调度
        try:
            success = self.task_manager.stop_scheduled_task(test_config_id)
            results['stop_schedule'] = self.print_test_result(
                "停止任务调度",
                success
            )
        except Exception as e:
            results['stop_schedule'] = self.print_test_result(
                "停止任务调度",
                False,
                f"异常: {e}"
            )
        
        self.test_results['schedule_management'] = results
        return results
    
    # ================== 批量执行和状态监控功能测试 ==================
    
    async def test_batch_operations(self):
        """测试批量执行和状态监控功能"""
        self.print_section_header("批量执行和状态监控功能测试")
        results = {}
        
        if not self.created_config_ids:
            logger.warning("⚠️ 没有可用的任务配置，跳过批量操作测试")
            return {}
        
        # 测试1: 立即执行单个任务（注意：这里可能会失败，因为需要Celery）
        try:
            task_id = await self.task_manager.execute_task_immediately(
                self.created_config_ids[0]
            )
            results['execute_immediate'] = self.print_test_result(
                "立即执行单个任务",
                task_id is not None,
                f"任务ID: {task_id}" if task_id else "无任务ID返回"
            )
        except Exception as e:
            results['execute_immediate'] = self.print_test_result(
                "立即执行单个任务",
                False,
                f"异常: {e}"
            )
        
        # 测试2: 批量执行多个任务
        if len(self.created_config_ids) > 1:
            try:
                task_ids = await self.task_manager.execute_multiple_tasks(
                    self.created_config_ids[:2]  # 取前两个
                )
                results['execute_multiple'] = self.print_test_result(
                    "批量执行多个任务",
                    isinstance(task_ids, list),
                    f"执行了 {len(task_ids)} 个任务"
                )
            except Exception as e:
                results['execute_multiple'] = self.print_test_result(
                    "批量执行多个任务",
                    False,
                    f"异常: {e}"
                )
        
        # 测试3: 按类型批量执行任务
        try:
            task_ids = await self.task_manager.execute_tasks_by_type("cleanup_tokens")
            results['execute_by_type'] = self.print_test_result(
                "按类型批量执行任务",
                isinstance(task_ids, list),
                f"执行了 {len(task_ids)} 个cleanup_tokens任务"
            )
        except Exception as e:
            results['execute_by_type'] = self.print_test_result(
                "按类型批量执行任务",
                False,
                f"异常: {e}"
            )
        
        # 测试4: 获取活跃的Celery任务
        try:
            active_tasks = self.task_manager.get_active_celery_tasks()
            results['get_active_tasks'] = self.print_test_result(
                "获取活跃的Celery任务",
                isinstance(active_tasks, list),
                f"找到 {len(active_tasks)} 个活跃任务"
            )
        except Exception as e:
            results['get_active_tasks'] = self.print_test_result(
                "获取活跃的Celery任务",
                False,
                f"异常: {e}"
            )
        
        self.test_results['batch_operations'] = results
        return results
    
    # ================== 任务健康度和统计功能测试 ==================
    
    async def test_health_statistics(self):
        """测试任务健康度和统计功能"""
        self.print_section_header("任务健康度和统计功能测试")
        results = {}
        
        # 测试1: 获取系统状态
        try:
            system_status = await self.task_manager.get_system_status()
            results['system_status'] = self.print_test_result(
                "获取系统状态",
                isinstance(system_status, dict) and 'scheduler_running' in system_status,
                f"调度器运行: {system_status.get('scheduler_running', 'unknown')}"
            )
            
            # 打印系统状态详情
            if isinstance(system_status, dict):
                logger.info("  📊 系统状态详情:")
                for key, value in system_status.items():
                    logger.info(f"    {key}: {value}")
                    
        except Exception as e:
            results['system_status'] = self.print_test_result(
                "获取系统状态",
                False,
                f"异常: {e}"
            )
        
        # 测试2: 获取全局健康度报告
        try:
            health_report = await self.task_manager.get_task_health_report()
            results['global_health'] = self.print_test_result(
                "获取全局健康度报告",
                isinstance(health_report, dict) and 'total_configs' in health_report,
                f"总配置数: {health_report.get('total_configs', 'unknown')}"
            )
            
            # 打印健康度报告详情
            if isinstance(health_report, dict):
                logger.info("  📈 全局健康度报告:")
                logger.info(f"    总配置数: {health_report.get('total_configs', 0)}")
                logger.info(f"    活跃配置数: {health_report.get('active_configs', 0)}")
                type_dist = health_report.get('type_distribution', {})
                if type_dist:
                    logger.info("    类型分布:")
                    for task_type, stats in type_dist.items():
                        logger.info(f"      {task_type}: {stats}")
                        
        except Exception as e:
            results['global_health'] = self.print_test_result(
                "获取全局健康度报告",
                False,
                f"异常: {e}"
            )
        
        # 测试3: 获取单个任务的健康度报告
        if self.created_config_ids:
            try:
                task_health = await self.task_manager.get_task_health_report(
                    self.created_config_ids[0]
                )
                results['task_health'] = self.print_test_result(
                    "获取单个任务健康度报告",
                    isinstance(task_health, dict) and 'config_id' in task_health,
                    f"配置ID: {task_health.get('config_id', 'unknown')}"
                )
            except Exception as e:
                results['task_health'] = self.print_test_result(
                    "获取单个任务健康度报告",
                    False,
                    f"异常: {e}"
                )
        
        # 测试4: 获取任务执行历史
        try:
            execution_history = await self.task_manager.get_task_execution_history(limit=10)
            results['execution_history'] = self.print_test_result(
                "获取任务执行历史",
                isinstance(execution_history, list),
                f"找到 {len(execution_history)} 条执行记录"
            )
        except Exception as e:
            results['execution_history'] = self.print_test_result(
                "获取任务执行历史",
                False,
                f"异常: {e}"
            )
        
        # 测试5: 获取调度事件
        try:
            schedule_events = await self.task_manager.get_task_schedule_events(limit=10)
            results['schedule_events'] = self.print_test_result(
                "获取调度事件",
                isinstance(schedule_events, list),
                f"找到 {len(schedule_events)} 个调度事件"
            )
        except Exception as e:
            results['schedule_events'] = self.print_test_result(
                "获取调度事件",
                False,
                f"异常: {e}"
            )
        
        self.test_results['health_statistics'] = results
        return results
    
    # ================== 系统管理功能测试 ==================
    
    async def test_system_management(self):
        """测试系统管理功能"""
        self.print_section_header("系统管理功能测试")
        results = {}
        
        # 测试1: 任务管理器启动状态检查
        try:
            # 通过获取系统状态来检查启动状态
            status = await self.task_manager.get_system_status()
            is_running = status.get('scheduler_running', False)
            results['manager_running'] = self.print_test_result(
                "任务管理器运行状态检查",
                is_running,
                f"调度器运行状态: {is_running}"
            )
        except Exception as e:
            results['manager_running'] = self.print_test_result(
                "任务管理器运行状态检查",
                False,
                f"异常: {e}"
            )
        
        # 测试2: 删除任务配置（测试部分配置）
        if len(self.created_config_ids) > 1:
            try:
                config_to_delete = self.created_config_ids.pop()  # 删除最后一个
                success = await self.task_manager.delete_task_config(config_to_delete)
                results['delete_config'] = self.print_test_result(
                    "删除任务配置",
                    success,
                    f"删除配置ID: {config_to_delete}"
                )
            except Exception as e:
                results['delete_config'] = self.print_test_result(
                    "删除任务配置",
                    False,
                    f"异常: {e}"
                )
        
        self.test_results['system_management'] = results
        return results
    
    # ================== 生成测试报告 ==================
    
    def generate_test_report(self):
        """生成详细的测试报告"""
        logger.info("📋 生成测试报告...")
        logger.info("=" * 80)
        logger.info("🎯 TasksManager 功能测试报告")
        logger.info("=" * 80)
        
        total_tests = 0
        passed_tests = 0
        
        for category, tests in self.test_results.items():
            if not tests:
                continue
                
            logger.info(f"\n📂 {category.upper()}:")
            for test_name, result in tests.items():
                total_tests += 1
                if result:
                    passed_tests += 1
                    status = "✅ PASS"
                else:
                    status = "❌ FAIL"
                logger.info(f"  {status} - {test_name}")
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        logger.info("=" * 80)
        logger.info(f"🏆 测试结果汇总:")
        logger.info(f"   总测试数: {total_tests}")
        logger.info(f"   通过数: {passed_tests}")
        logger.info(f"   失败数: {total_tests - passed_tests}")
        logger.info(f"   成功率: {success_rate:.1f}%")
        logger.info("=" * 80)
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'success_rate': success_rate,
            'details': self.test_results
        }


async def main():
    """主测试函数"""
    logger.info("🚀 开始 TasksManager 完整功能测试")
    
    tester = TasksManagerTester()
    
    try:
        # 初始化测试环境
        if not await tester.setup():
            logger.error("❌ 测试环境初始化失败，退出测试")
            return
        
        # 等待服务完全启动
        logger.info("⏰ 等待服务完全启动...")
        await asyncio.sleep(3)
        
        # 运行所有测试
        await tester.test_config_management()
        await asyncio.sleep(1)
        
        await tester.test_schedule_management()
        await asyncio.sleep(1)
        
        await tester.test_batch_operations()
        await asyncio.sleep(1)
        
        await tester.test_health_statistics()
        await asyncio.sleep(1)
        
        await tester.test_system_management()
        
        # 生成测试报告
        report = tester.generate_test_report()
        
    except Exception as e:
        logger.error(f"❌ 测试过程中发生严重错误: {e}")
        
    finally:
        # 清理测试环境
        await tester.cleanup()
    
    logger.info("🎉 TasksManager 功能测试完成!")


if __name__ == "__main__":
    asyncio.run(main())
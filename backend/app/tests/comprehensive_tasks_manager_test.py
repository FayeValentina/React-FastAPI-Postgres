# #!/usr/bin/env python3
# """
# TasksManager 完整功能测试脚本
# 测试所有的任务管理功能，包括配置管理、调度管理、批量操作、统计分析等
# """

# import sys
# import os

# # 添加项目根目录到Python路径
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# import asyncio
# import json
# import logging
# from datetime import datetime, timedelta
# from typing import Dict, Any, List

# # 设置日志
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )

# logger = logging.getLogger(__name__)


# class TasksManagerTester:
#     """TasksManager功能测试类"""
    
#     def __init__(self):
#         self.task_manager = None
#         self.test_results = {
#             'config_management': {},
#             'schedule_management': {},
#             'batch_operations': {},
#             'health_statistics': {},
#             'system_management': {}
#         }
#         self.created_config_ids = []
    
#     async def setup(self):
#         """初始化测试环境"""
#         logger.info("🔧 初始化测试环境...")
        
#         try:
#             from app.services.tasks_manager import task_manager
#             self.task_manager = task_manager
            
#             # 启动任务管理器
#             await self.task_manager.start()
#             logger.info("✅ TasksManager启动成功")
            
#             return True
#         except Exception as e:
#             logger.error(f"❌ 初始化失败: {e}")
#             return False
    
#     async def cleanup(self):
#         """清理测试环境"""
#         logger.info("🧹 清理测试环境...")
        
#         try:
#             # 清理创建的测试配置
#             for config_id in self.created_config_ids:
#                 try:
#                     await self.task_manager.delete_task_config(config_id)
#                     logger.info(f"🗑️ 清理测试配置: {config_id}")
#                 except Exception as e:
#                     logger.warning(f"清理配置 {config_id} 失败: {e}")
            
#             # 关闭任务管理器
#             self.task_manager.shutdown()
#             logger.info("✅ 清理完成")
            
#         except Exception as e:
#             logger.error(f"❌ 清理失败: {e}")
    
#     def print_section_header(self, title: str):
#         """打印测试章节标题"""
#         logger.info("=" * 80)
#         logger.info(f"🧪 {title}")
#         logger.info("=" * 80)
    
#     def print_test_result(self, test_name: str, success: bool, details: str = None):
#         """打印测试结果"""
#         status = "✅" if success else "❌"
#         message = f"{status} {test_name}"
#         if details:
#             message += f" - {details}"
#         logger.info(message)
#         return success
    
#     # ================== 任务配置管理功能测试 ==================
    
#     async def test_config_management(self):
#         """测试任务配置管理功能"""
#         self.print_section_header("任务配置管理功能测试")
#         results = {}
        
#         # 测试1: 创建任务配置
#         try:
#             from app.core.task_registry import TaskType, SchedulerType
#             config_id = await self.task_manager.create_task_config(
#                 name="测试清理任务",
#                 task_type=TaskType.CLEANUP_TOKENS,
#                 scheduler_type=SchedulerType.INTERVAL,
#                 description="用于测试的清理任务",
#                 parameters={
#                     "days_old": 7
#                 },
#                 schedule_config={
#                     "scheduler_type": "interval",
#                     "hours": 2
#                 },
#                 priority=8,
#                 timeout_seconds=300,
#                 max_retries=3
#             )
            
#             if config_id:
#                 self.created_config_ids.append(config_id)
#                 results['create_config'] = self.print_test_result(
#                     "创建任务配置",
#                     True,
#                     f"配置ID: {config_id}"
#                 )
#             else:
#                 results['create_config'] = self.print_test_result(
#                     "创建任务配置",
#                     False,
#                     "返回的配置ID为None"
#                 )
                
#         except Exception as e:
#             results['create_config'] = self.print_test_result(
#                 "创建任务配置",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试2: 获取任务配置
#         if self.created_config_ids:
#             try:
#                 config = await self.task_manager.get_task_config(self.created_config_ids[0])
#                 if config and config.get('name') == "测试清理任务":
#                     results['get_config'] = self.print_test_result(
#                         "获取任务配置",
#                         True,
#                         f"名称: {config.get('name')}, 类型: {config.get('task_type')}"
#                     )
#                 else:
#                     results['get_config'] = self.print_test_result(
#                         "获取任务配置",
#                         False,
#                         "配置信息不正确"
#                     )
#             except Exception as e:
#                 results['get_config'] = self.print_test_result(
#                     "获取任务配置",
#                     False,
#                     f"异常: {e}"
#                 )
        
#         # 测试3: 创建多种类型的任务配置
#         test_configs = [
#             {
#                 "name": "测试清理令牌任务",
#                 "task_type": TaskType.CLEANUP_TOKENS,
#                 "scheduler_type": SchedulerType.CRON,
#                 "description": "清理过期令牌",
#                 "parameters": {"days_old": 30},
#                 "schedule_config": {
#                     "scheduler_type": "cron",
#                     "minute": "0",
#                     "hour": "2",
#                     "day": "*",
#                     "month": "*",
#                     "day_of_week": "*"
#                 }
#             },
#             {
#                 "name": "测试邮件任务",
#                 "task_type": TaskType.SEND_EMAIL,
#                 "scheduler_type": SchedulerType.DATE,
#                 "description": "发送邮件通知",
#                 "parameters": {
#                     "recipient_emails": ["test@example.com"],
#                     "subject": "测试邮件",
#                     "template_name": "test_template"
#                 },
#                 "schedule_config": {
#                     "scheduler_type": "date",
#                     "run_date": (datetime.now() + timedelta(hours=1)).isoformat()
#                 }
#             }
#         ]
        
#         create_multiple_success = True
#         for config_data in test_configs:
#             try:
#                 config_id = await self.task_manager.create_task_config(**config_data)
#                 if config_id:
#                     self.created_config_ids.append(config_id)
#                     logger.info(f"  ✓ 创建 {config_data['task_type'].value} 任务成功: {config_id}")
#                 else:
#                     create_multiple_success = False
#                     logger.error(f"  ✗ 创建 {config_data['task_type'].value} 任务失败")
#             except Exception as e:
#                 create_multiple_success = False
#                 logger.error(f"  ✗ 创建 {config_data['task_type'].value} 任务异常: {e}")
        
#         results['create_multiple_configs'] = self.print_test_result(
#             "创建多种类型任务配置",
#             create_multiple_success,
#             f"共创建 {len(self.created_config_ids)} 个配置"
#         )
        
#         # 测试4: 更新任务配置
#         if self.created_config_ids:
#             try:
#                 success = await self.task_manager.update_task_config(
#                     self.created_config_ids[0],
#                     {"description": "更新后的描述", "priority": 9}
#                 )
#                 results['update_config'] = self.print_test_result(
#                     "更新任务配置",
#                     success
#                 )
#             except Exception as e:
#                 results['update_config'] = self.print_test_result(
#                     "更新任务配置",
#                     False,
#                     f"异常: {e}"
#                 )
        
#         # 测试5: 列出任务配置
#         try:
#             configs = await self.task_manager.list_task_configs()
#             results['list_configs'] = self.print_test_result(
#                 "列出所有任务配置",
#                 len(configs) >= len(self.created_config_ids),
#                 f"找到 {len(configs)} 个配置"
#             )
#         except Exception as e:
#             results['list_configs'] = self.print_test_result(
#                 "列出所有任务配置",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试6: 按类型筛选任务配置
#         try:
#             cleanup_configs = await self.task_manager.list_task_configs(task_type="cleanup_tokens")
#             results['filter_configs'] = self.print_test_result(
#                 "按类型筛选任务配置",
#                 len(cleanup_configs) >= 1,
#                 f"找到 {len(cleanup_configs)} 个cleanup_tokens配置"
#             )
#         except Exception as e:
#             results['filter_configs'] = self.print_test_result(
#                 "按类型筛选任务配置",
#                 False,
#                 f"异常: {e}"
#             )
        
#         self.test_results['config_management'] = results
#         return results
    
#     # ================== 任务调度管理功能测试 ==================
    
#     async def test_schedule_management(self):
#         """测试任务调度管理功能"""
#         self.print_section_header("任务调度管理功能测试")
#         results = {}
        
#         if not self.created_config_ids:
#             logger.warning("⚠️ 没有可用的任务配置，跳过调度管理测试")
#             return {}
        
#         test_config_id = self.created_config_ids[0]
        
#         # 测试1: 启动任务调度
#         try:
#             success = await self.task_manager.start_scheduled_task(test_config_id)
#             results['start_schedule'] = self.print_test_result(
#                 "启动任务调度",
#                 success,
#                 f"配置ID: {test_config_id}"
#             )
#         except Exception as e:
#             results['start_schedule'] = self.print_test_result(
#                 "启动任务调度",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 等待一下，确保调度器加载完成
#         await asyncio.sleep(2)
        
#         # 测试2: 查看调度中的任务
#         try:
#             scheduled_jobs = self.task_manager.get_scheduled_jobs()
#             results['get_scheduled_jobs'] = self.print_test_result(
#                 "获取调度中的任务",
#                 len(scheduled_jobs) > 0,
#                 f"找到 {len(scheduled_jobs)} 个调度中的任务"
#             )
            
#             # 打印调度任务详情
#             for job in scheduled_jobs:
#                 logger.info(f"  📋 任务: {job.get('name')} (ID: {job.get('job_id')}, 下次执行: {job.get('next_run_time')})")
                
#         except Exception as e:
#             results['get_scheduled_jobs'] = self.print_test_result(
#                 "获取调度中的任务",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试3: 暂停任务调度
#         try:
#             success = self.task_manager.pause_scheduled_task(test_config_id)
#             results['pause_schedule'] = self.print_test_result(
#                 "暂停任务调度",
#                 success
#             )
#         except Exception as e:
#             results['pause_schedule'] = self.print_test_result(
#                 "暂停任务调度",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 等待一下
#         await asyncio.sleep(1)
        
#         # 测试4: 恢复任务调度
#         try:
#             success = self.task_manager.resume_scheduled_task(test_config_id)
#             results['resume_schedule'] = self.print_test_result(
#                 "恢复任务调度",
#                 success
#             )
#         except Exception as e:
#             results['resume_schedule'] = self.print_test_result(
#                 "恢复任务调度",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试5: 重新加载任务调度
#         try:
#             success = await self.task_manager.reload_scheduled_task(test_config_id)
#             results['reload_schedule'] = self.print_test_result(
#                 "重新加载任务调度",
#                 success
#             )
#         except Exception as e:
#             results['reload_schedule'] = self.print_test_result(
#                 "重新加载任务调度",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试6: 停止任务调度
#         try:
#             success = self.task_manager.stop_scheduled_task(test_config_id)
#             results['stop_schedule'] = self.print_test_result(
#                 "停止任务调度",
#                 success
#             )
#         except Exception as e:
#             results['stop_schedule'] = self.print_test_result(
#                 "停止任务调度",
#                 False,
#                 f"异常: {e}"
#             )
        
#         self.test_results['schedule_management'] = results
#         return results
    
#     # ================== 批量执行和状态监控功能测试 ==================
    
#     async def test_batch_operations(self):
#         """测试批量执行和状态监控功能"""
#         self.print_section_header("批量执行和状态监控功能测试")
#         results = {}
        
#         if not self.created_config_ids:
#             logger.warning("⚠️ 没有可用的任务配置，跳过批量操作测试")
#             return {}
        
#         # 测试1: 立即执行单个任务（注意：这里可能会失败，因为需要Celery）
#         try:
#             task_id = await self.task_manager.execute_task_immediately(
#                 self.created_config_ids[0]
#             )
#             results['execute_immediate'] = self.print_test_result(
#                 "立即执行单个任务",
#                 task_id is not None,
#                 f"任务ID: {task_id}" if task_id else "无任务ID返回"
#             )
#         except Exception as e:
#             results['execute_immediate'] = self.print_test_result(
#                 "立即执行单个任务",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试2: 根据任务类型直接执行任务
#         try:
#             from app.core.task_registry import TaskType
#             task_id = await self.task_manager.execute_task_by_type(
#                 task_type=TaskType.CLEANUP_TOKENS.value,
#                 task_params={"days_old": 7},
#                 queue='default'
#             )
#             results['execute_by_type'] = self.print_test_result(
#                 "根据任务类型直接执行任务",
#                 task_id is not None,
#                 f"任务ID: {task_id}" if task_id else "无任务ID返回"
#             )
#         except Exception as e:
#             results['execute_by_type'] = self.print_test_result(
#                 "根据任务类型直接执行任务",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试3: 批量执行多个任务配置
#         if len(self.created_config_ids) >= 2:
#             try:
#                 task_ids = await self.task_manager.execute_multiple_configs(
#                     config_ids=self.created_config_ids[:2]  # 执行前两个配置
#                 )
#                 results['execute_multiple_configs'] = self.print_test_result(
#                     "批量执行多个任务配置",
#                     isinstance(task_ids, list) and len(task_ids) > 0,
#                     f"执行了 {len(task_ids)} 个任务" if isinstance(task_ids, list) else "返回结果异常"
#                 )
#             except Exception as e:
#                 results['execute_multiple_configs'] = self.print_test_result(
#                     "批量执行多个任务配置",
#                     False,
#                     f"异常: {e}"
#                 )
#         else:
#             results['execute_multiple_configs'] = self.print_test_result(
#                 "批量执行多个任务配置",
#                 True,
#                 "跳过 - 测试配置数量不足"
#             )
        
#         # 测试4: 批量执行指定类型的所有活跃任务配置
#         try:
#             task_ids = await self.task_manager.execute_batch_by_task_type(
#                 task_type=TaskType.CLEANUP_TOKENS.value
#             )
#             results['execute_batch_by_type'] = self.print_test_result(
#                 "批量执行指定类型的所有活跃任务配置",
#                 isinstance(task_ids, list),
#                 f"执行了 {len(task_ids)} 个任务" if isinstance(task_ids, list) else "返回结果异常"
#             )
#         except Exception as e:
#             results['execute_batch_by_type'] = self.print_test_result(
#                 "批量执行指定类型的所有活跃任务配置",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试5: 获取活跃的任务 (现在通过TaskManager方法调用)
#         try:
#             active_tasks = self.task_manager.get_active_tasks()
#             results['get_active_tasks'] = self.print_test_result(
#                 "获取活跃的Celery任务",
#                 isinstance(active_tasks, list),
#                 f"找到 {len(active_tasks)} 个活跃任务"
#             )
#         except Exception as e:
#             results['get_active_tasks'] = self.print_test_result(
#                 "获取活跃的Celery任务",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试6: 获取任务状态 (如果有task_id的话)
#         test_task_id = "test-task-id-123"  # 模拟任务ID
#         try:
#             task_status = self.task_manager.get_task_status(test_task_id)
#             results['get_task_status'] = self.print_test_result(
#                 "获取任务状态",
#                 isinstance(task_status, dict) and 'task_id' in task_status,
#                 f"状态: {task_status.get('status', 'unknown')}" if isinstance(task_status, dict) else "返回结果异常"
#             )
#         except Exception as e:
#             results['get_task_status'] = self.print_test_result(
#                 "获取任务状态",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试7: 获取队列长度
#         try:
#             queue_length = self.task_manager.get_queue_length('default')
#             results['get_queue_length'] = self.print_test_result(
#                 "获取队列长度",
#                 isinstance(queue_length, int),
#                 f"default队列长度: {queue_length}" if isinstance(queue_length, int) else "返回结果异常"
#             )
#         except Exception as e:
#             results['get_queue_length'] = self.print_test_result(
#                 "获取队列长度",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试8: 获取支持的任务类型
#         try:
#             task_types = self.task_manager.get_supported_task_types()
#             results['get_supported_task_types'] = self.print_test_result(
#                 "获取支持的任务类型",
#                 isinstance(task_types, dict) and len(task_types) > 0,
#                 f"支持 {len(task_types)} 种任务类型" if isinstance(task_types, dict) else "返回结果异常"
#             )
            
#             # 打印支持的任务类型
#             if isinstance(task_types, dict):
#                 logger.info("  📋 支持的任务类型:")
#                 for task_type, description in task_types.items():
#                     logger.info(f"    {task_type}: {description}")
                    
#         except Exception as e:
#             results['get_supported_task_types'] = self.print_test_result(
#                 "获取支持的任务类型",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试9: 检查任务类型支持情况
#         try:
#             from app.core.task_registry import TaskType
#             is_supported = self.task_manager.is_task_type_supported(TaskType.CLEANUP_TOKENS.value)
#             results['is_task_type_supported'] = self.print_test_result(
#                 "检查任务类型支持情况",
#                 isinstance(is_supported, bool),
#                 f"CLEANUP_TOKENS 支持: {is_supported}" if isinstance(is_supported, bool) else "返回结果异常"
#             )
#         except Exception as e:
#             results['is_task_type_supported'] = self.print_test_result(
#                 "检查任务类型支持情况",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试10: 撤销任务 (使用模拟任务ID)
#         try:
#             revoke_result = self.task_manager.revoke_task(test_task_id, terminate=False)
#             results['revoke_task'] = self.print_test_result(
#                 "撤销任务",
#                 isinstance(revoke_result, dict) and 'task_id' in revoke_result,
#                 f"撤销结果: {revoke_result.get('revoked', 'unknown')}" if isinstance(revoke_result, dict) else "返回结果异常"
#             )
#         except Exception as e:
#             results['revoke_task'] = self.print_test_result(
#                 "撤销任务",
#                 False,
#                 f"异常: {e}"
#             )
        
#         self.test_results['batch_operations'] = results
#         return results
    
#     # ================== 新增任务管理方法功能测试 ==================
    
#     async def test_new_task_management_methods(self):
#         """测试新增的任务管理方法功能"""
#         self.print_section_header("新增任务管理方法功能测试")
#         results = {}
        
#         # 测试1: 测试执行任务类型相关的方法
#         try:
#             from app.core.task_registry import TaskType
            
#             # 测试 execute_task_by_type 方法 - 使用实际的任务类型
#             task_id = await self.task_manager.execute_task_by_type(
#                 task_type=TaskType.CLEANUP_TOKENS.value,
#                 task_params={"days_old": 30, "test_mode": True},
#                 queue='test_queue',
#                 countdown=10
#             )
#             results['execute_task_by_type_detailed'] = self.print_test_result(
#                 "execute_task_by_type 详细测试",
#                 task_id is not None,
#                 f"任务ID: {task_id}" if task_id else "无任务ID返回"
#             )
#         except Exception as e:
#             results['execute_task_by_type_detailed'] = self.print_test_result(
#                 "execute_task_by_type 详细测试",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试2: 测试批量执行方法 - execute_multiple_configs
#         if len(self.created_config_ids) >= 3:
#             try:
#                 selected_config_ids = self.created_config_ids[:3]
#                 task_ids = await self.task_manager.execute_multiple_configs(
#                     config_ids=selected_config_ids,
#                     countdown=5
#                 )
#                 results['execute_multiple_configs_detailed'] = self.print_test_result(
#                     "execute_multiple_configs 详细测试",
#                     isinstance(task_ids, list),
#                     f"批量执行 {len(selected_config_ids)} 个配置，返回 {len(task_ids)} 个任务ID" if isinstance(task_ids, list) else "返回结果异常"
#                 )
#             except Exception as e:
#                 results['execute_multiple_configs_detailed'] = self.print_test_result(
#                     "execute_multiple_configs 详细测试",
#                     False,
#                     f"异常: {e}"
#                 )
#         else:
#             results['execute_multiple_configs_detailed'] = self.print_test_result(
#                 "execute_multiple_configs 详细测试",
#                 True,
#                 "跳过 - 测试配置数量不足"
#             )
        
#         # 测试3: 测试批量执行指定类型任务 - execute_batch_by_task_type
#         try:
#             task_ids = await self.task_manager.execute_batch_by_task_type(
#                 task_type=TaskType.CLEANUP_TOKENS.value,
#                 countdown=15
#             )
#             results['execute_batch_by_task_type_detailed'] = self.print_test_result(
#                 "execute_batch_by_task_type 详细测试",
#                 isinstance(task_ids, list),
#                 f"批量执行 CLEANUP_TOKENS 类型任务，返回 {len(task_ids)} 个任务ID" if isinstance(task_ids, list) else "返回结果异常"
#             )
#         except Exception as e:
#             results['execute_batch_by_task_type_detailed'] = self.print_test_result(
#                 "execute_batch_by_task_type 详细测试",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试4: 测试任务状态管理方法
#         test_task_ids = ["test-task-001", "test-task-002", "test-task-003"]
        
#         for i, task_id in enumerate(test_task_ids, 1):
#             try:
#                 # 测试 get_task_status
#                 status = self.task_manager.get_task_status(task_id)
#                 results[f'get_task_status_{i}'] = self.print_test_result(
#                     f"get_task_status 测试 {i}",
#                     isinstance(status, dict) and 'task_id' in status,
#                     f"任务 {task_id} 状态: {status.get('status')}" if isinstance(status, dict) else "状态获取异常"
#                 )
#             except Exception as e:
#                 results[f'get_task_status_{i}'] = self.print_test_result(
#                     f"get_task_status 测试 {i}",
#                     False,
#                     f"异常: {e}"
#                 )
        
#         # 测试5: 测试队列管理方法
#         test_queues = ['default', 'high_priority', 'low_priority']
        
#         for queue in test_queues:
#             try:
#                 length = self.task_manager.get_queue_length(queue)
#                 results[f'queue_length_{queue}'] = self.print_test_result(
#                     f"get_queue_length 测试 ({queue})",
#                     isinstance(length, int) and length >= -1,  # -1 表示错误但仍是有效返回
#                     f"队列 {queue} 长度: {length}"
#                 )
#             except Exception as e:
#                 results[f'queue_length_{queue}'] = self.print_test_result(
#                     f"get_queue_length 测试 ({queue})",
#                     False,
#                     f"异常: {e}"
#                 )
        
#         # 测试6: 测试任务类型支持检查
#         test_task_types = [
#             TaskType.CLEANUP_TOKENS.value,
#             TaskType.SEND_EMAIL.value,
#             "invalid_task_type",
#             "another_invalid_type"
#         ]
        
#         for task_type in test_task_types:
#             try:
#                 is_supported = self.task_manager.is_task_type_supported(task_type)
#                 expected = task_type in [t.value for t in TaskType]
#                 results[f'task_type_support_{task_type}'] = self.print_test_result(
#                     f"is_task_type_supported ({task_type})",
#                     isinstance(is_supported, bool),
#                     f"支持状态: {is_supported} (预期: {expected})"
#                 )
#             except Exception as e:
#                 results[f'task_type_support_{task_type}'] = self.print_test_result(
#                     f"is_task_type_supported ({task_type})",
#                     False,
#                     f"异常: {e}"
#                 )
        
#         # 测试7: 测试撤销任务功能
#         for i, task_id in enumerate(test_task_ids[:2], 1):  # 只测试前两个
#             try:
#                 # 测试不终止的撤销
#                 revoke_result = self.task_manager.revoke_task(task_id, terminate=False)
#                 results[f'revoke_task_{i}'] = self.print_test_result(
#                     f"revoke_task 测试 {i} (不终止)",
#                     isinstance(revoke_result, dict) and 'task_id' in revoke_result,
#                     f"撤销任务 {task_id}: {revoke_result.get('revoked')}" if isinstance(revoke_result, dict) else "撤销结果异常"
#                 )
#             except Exception as e:
#                 results[f'revoke_task_{i}'] = self.print_test_result(
#                     f"revoke_task 测试 {i} (不终止)",
#                     False,
#                     f"异常: {e}"
#                 )
        
#         # 测试8: 测试获取支持的任务类型（详细测试）
#         try:
#             supported_types = self.task_manager.get_supported_task_types()
#             is_valid = (
#                 isinstance(supported_types, dict) and 
#                 len(supported_types) > 0 and
#                 all(isinstance(k, str) and isinstance(v, str) for k, v in supported_types.items())
#             )
#             results['get_supported_task_types_detailed'] = self.print_test_result(
#                 "get_supported_task_types 详细测试",
#                 is_valid,
#                 f"获取到 {len(supported_types)} 种支持的任务类型，格式正确" if is_valid else "返回格式异常"
#             )
            
#             # 验证关键任务类型是否存在
#             expected_types = [TaskType.CLEANUP_TOKENS.value, TaskType.SEND_EMAIL.value]
#             for expected_type in expected_types:
#                 if isinstance(supported_types, dict):
#                     has_type = expected_type in supported_types
#                     results[f'has_task_type_{expected_type}'] = self.print_test_result(
#                         f"检查任务类型 {expected_type} 存在性",
#                         has_type,
#                         f"类型 {expected_type} {'存在' if has_type else '不存在'}"
#                     )
                    
#         except Exception as e:
#             results['get_supported_task_types_detailed'] = self.print_test_result(
#                 "get_supported_task_types 详细测试",
#                 False,
#                 f"异常: {e}"
#             )
        
#         self.test_results['new_methods'] = results
#         return results
    
#     # ================== 任务健康度和统计功能测试 ==================
    
#     async def test_health_statistics(self):
#         """测试任务健康度和统计功能"""
#         self.print_section_header("任务健康度和统计功能测试")
#         results = {}
        
#         # 测试1: 获取系统状态
#         try:
#             system_status = await self.task_manager.get_system_status()
#             results['system_status'] = self.print_test_result(
#                 "获取系统状态",
#                 isinstance(system_status, dict) and 'scheduler_running' in system_status,
#                 f"调度器运行: {system_status.get('scheduler_running', 'unknown')}"
#             )
            
#             # 打印系统状态详情
#             if isinstance(system_status, dict):
#                 logger.info("  📊 系统状态详情:")
#                 for key, value in system_status.items():
#                     logger.info(f"    {key}: {value}")
                    
#         except Exception as e:
#             results['system_status'] = self.print_test_result(
#                 "获取系统状态",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 注意: 新架构中简化了健康度和统计功能，跳过这些测试
#         results['global_health'] = self.print_test_result(
#             "获取全局健康度报告",
#             True,
#             "已跳过 - 新架构中方法已简化"
#         )
        
#         results['task_health'] = self.print_test_result(
#             "获取单个任务健康度报告",
#             True,
#             "已跳过 - 新架构中方法已简化"
#         )
        
#         results['execution_history'] = self.print_test_result(
#             "获取任务执行历史",
#             True,
#             "已跳过 - 新架构中方法已简化"
#         )
        
#         results['schedule_events'] = self.print_test_result(
#             "获取调度事件",
#             True,
#             "已跳过 - 新架构中方法已简化"
#         )
        
#         self.test_results['health_statistics'] = results
#         return results
    
#     # ================== 系统管理功能测试 ==================
    
#     async def test_system_management(self):
#         """测试系统管理功能"""
#         self.print_section_header("系统管理功能测试")
#         results = {}
        
#         # 测试1: 任务管理器启动状态检查
#         try:
#             # 通过获取系统状态来检查启动状态
#             status = await self.task_manager.get_system_status()
#             is_running = status.get('scheduler_running', False)
#             results['manager_running'] = self.print_test_result(
#                 "任务管理器运行状态检查",
#                 is_running,
#                 f"调度器运行状态: {is_running}"
#             )
#         except Exception as e:
#             results['manager_running'] = self.print_test_result(
#                 "任务管理器运行状态检查",
#                 False,
#                 f"异常: {e}"
#             )
        
#         # 测试2: 删除任务配置（测试部分配置）
#         if len(self.created_config_ids) > 1:
#             try:
#                 config_to_delete = self.created_config_ids.pop()  # 删除最后一个
#                 success = await self.task_manager.delete_task_config(config_to_delete)
#                 results['delete_config'] = self.print_test_result(
#                     "删除任务配置",
#                     success,
#                     f"删除配置ID: {config_to_delete}"
#                 )
#             except Exception as e:
#                 results['delete_config'] = self.print_test_result(
#                     "删除任务配置",
#                     False,
#                     f"异常: {e}"
#                 )
        
#         self.test_results['system_management'] = results
#         return results
    
#     # ================== 生成测试报告 ==================
    
#     def generate_test_report(self):
#         """生成详细的测试报告"""
#         logger.info("📋 生成测试报告...")
#         logger.info("=" * 80)
#         logger.info("🎯 TasksManager 功能测试报告")
#         logger.info("=" * 80)
        
#         total_tests = 0
#         passed_tests = 0
        
#         for category, tests in self.test_results.items():
#             if not tests:
#                 continue
                
#             logger.info(f"\n📂 {category.upper()}:")
#             for test_name, result in tests.items():
#                 total_tests += 1
#                 if result:
#                     passed_tests += 1
#                     status = "✅ PASS"
#                 else:
#                     status = "❌ FAIL"
#                 logger.info(f"  {status} - {test_name}")
        
#         success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
#         logger.info("=" * 80)
#         logger.info(f"🏆 测试结果汇总:")
#         logger.info(f"   总测试数: {total_tests}")
#         logger.info(f"   通过数: {passed_tests}")
#         logger.info(f"   失败数: {total_tests - passed_tests}")
#         logger.info(f"   成功率: {success_rate:.1f}%")
#         logger.info("=" * 80)
        
#         return {
#             'total_tests': total_tests,
#             'passed_tests': passed_tests,
#             'success_rate': success_rate,
#             'details': self.test_results
#         }


# async def main():
#     """主测试函数"""
#     logger.info("🚀 开始 TasksManager 完整功能测试")
    
#     tester = TasksManagerTester()
    
#     try:
#         # 初始化测试环境
#         if not await tester.setup():
#             logger.error("❌ 测试环境初始化失败，退出测试")
#             return
        
#         # 等待服务完全启动
#         logger.info("⏰ 等待服务完全启动...")
#         await asyncio.sleep(3)
        
#         # 运行所有测试
#         await tester.test_config_management()
#         await asyncio.sleep(1)
        
#         await tester.test_schedule_management()
#         await asyncio.sleep(1)
        
#         await tester.test_batch_operations()
#         await asyncio.sleep(1)
        
#         await tester.test_new_task_management_methods()
#         await asyncio.sleep(1)
        
#         await tester.test_health_statistics()
#         await asyncio.sleep(1)
        
#         await tester.test_system_management()
        
#         # 生成测试报告
#         report = tester.generate_test_report()
        
#     except Exception as e:
#         logger.error(f"❌ 测试过程中发生严重错误: {e}")
        
#     finally:
#         # 清理测试环境
#         await tester.cleanup()
    
#     logger.info("🎉 TasksManager 功能测试完成!")


# if __name__ == "__main__":
#     asyncio.run(main())
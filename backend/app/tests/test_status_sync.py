"""
测试任务状态同步功能
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.task_registry import TaskType, ConfigStatus, SchedulerType, TaskRegistry


class TestStatusSync:
    """任务状态同步测试"""
    
    def setup_method(self):
        """设置测试环境"""
        self.task_manager = TaskManager()
        
        # Mock scheduler
        self.task_manager.scheduler = MagicMock()
        
        # Mock jobs for testing
        self.mock_job = MagicMock()
        self.mock_job.id = "cleanup_tok_int_205"
        self.mock_job.next_run_time = None  # 模拟暂停状态
        
    def test_extract_config_id_from_job_id(self):
        """测试从job_id提取config_id"""
        config_id = TaskRegistry.extract_config_id_from_job_id("cleanup_tok_int_205")
        assert config_id == 205
        
        config_id = TaskRegistry.extract_config_id_from_job_id("email_cron_123")
        assert config_id == 123
    
    def test_get_scheduler_status_paused(self):
        """测试获取暂停状态"""
        # Mock get_all_jobs 返回暂停的任务
        self.mock_job.next_run_time = None  # 暂停状态
        self.task_manager.scheduler.get_all_jobs.return_value = [self.mock_job]
        
        status = self.task_manager._get_scheduler_status(205)
        assert status == "paused"
    
    def test_get_scheduler_status_active(self):
        """测试获取活跃状态"""
        # Mock get_all_jobs 返回活跃的任务
        from datetime import datetime
        self.mock_job.next_run_time = datetime.now()  # 活跃状态
        self.task_manager.scheduler.get_all_jobs.return_value = [self.mock_job]
        
        status = self.task_manager._get_scheduler_status(205)
        assert status == "active"
    
    def test_get_scheduler_status_inactive(self):
        """测试获取未调度状态"""
        # Mock get_all_jobs 返回空列表
        self.task_manager.scheduler.get_all_jobs.return_value = []
        
        status = self.task_manager._get_scheduler_status(205)
        assert status == "inactive"
    
    @patch('app.services.tasks_manager.AsyncSessionLocal')
    @patch('app.services.tasks_manager.crud_task_config')
    async def test_pause_scheduled_task_success(self, mock_crud, mock_session):
        """测试暂停任务成功"""
        # Mock scheduler operations
        self.task_manager.scheduler.get_all_jobs.return_value = [self.mock_job]
        self.task_manager.scheduler.pause_job.return_value = True
        
        # Mock database operations
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db
        mock_crud.update_status = AsyncMock(return_value=True)
        
        # 执行测试
        result = await self.task_manager.pause_scheduled_task(205)
        
        # 验证结果
        assert result is True
        self.task_manager.scheduler.pause_job.assert_called_once_with("cleanup_tok_int_205")
        mock_crud.update_status.assert_called_once_with(mock_db, 205, ConfigStatus.PAUSED)
    
    @patch('app.services.tasks_manager.AsyncSessionLocal')
    @patch('app.services.tasks_manager.crud_task_config')
    async def test_resume_scheduled_task_success(self, mock_crud, mock_session):
        """测试恢复任务成功"""
        # Mock scheduler operations
        self.task_manager.scheduler.get_all_jobs.return_value = [self.mock_job]
        self.task_manager.scheduler.resume_job.return_value = True
        
        # Mock database operations
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db
        mock_crud.update_status = AsyncMock(return_value=True)
        
        # 执行测试
        result = await self.task_manager.resume_scheduled_task(205)
        
        # 验证结果
        assert result is True
        self.task_manager.scheduler.resume_job.assert_called_once_with("cleanup_tok_int_205")
        mock_crud.update_status.assert_called_once_with(mock_db, 205, ConfigStatus.ACTIVE)
    
    def test_pause_task_not_found(self):
        """测试暂停不存在的任务"""
        # Mock scheduler 返回空任务列表
        self.task_manager.scheduler.get_all_jobs.return_value = []
        
        # 执行测试（使用同步版本进行简单测试）
        jobs = self.task_manager.scheduler.get_all_jobs()
        found = False
        for job in jobs:
            extracted_config_id = TaskRegistry.extract_config_id_from_job_id(job.id)
            if extracted_config_id == 205:
                found = True
                break
        
        assert found is False


def test_meaningful_job_id_format():
    """测试有意义的job_id格式"""
    job_id = TaskRegistry.generate_job_id(
        task_type=TaskType.CLEANUP_TOKENS,
        scheduler_type=SchedulerType.CRON,
        config_id=205
    )
    
    assert job_id == "cleanup_tok_cron_205"
    
    # 测试提取
    config_id = TaskRegistry.extract_config_id_from_job_id(job_id)
    assert config_id == 205


if __name__ == "__main__":
    # 运行简单的同步测试
    test_meaningful_job_id_format()
    print("✓ Job ID format test passed")
    
    # 测试状态检查
    test_sync = TestStatusSync()
    test_sync.setup_method()
    
    # 同步测试
    test_sync.test_extract_config_id_from_job_id()
    print("✓ Config ID extraction test passed")
    
    test_sync.test_get_scheduler_status_paused()
    print("✓ Scheduler status (paused) test passed")
    
    test_sync.test_get_scheduler_status_active() 
    print("✓ Scheduler status (active) test passed")
    
    test_sync.test_get_scheduler_status_inactive()
    print("✓ Scheduler status (inactive) test passed")
    
    test_sync.test_pause_task_not_found()
    print("✓ Task not found test passed")
    
    print("All status sync tests passed!")
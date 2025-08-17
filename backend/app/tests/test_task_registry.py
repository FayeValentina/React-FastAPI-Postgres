import pytest
from app.constant.task_registry import TaskRegistry, TaskType, SchedulerType


def test_generate_job_id():
    """测试job_id生成"""
    job_id = TaskRegistry.generate_job_id(
        task_type=TaskType.CLEANUP_TOKENS,
        scheduler_type=SchedulerType.CRON,
        config_id=1
    )
    assert job_id == "cleanup_tok_cron_1"


def test_generate_job_id_cron():
    """测试生成cron任务的job_id"""
    job_id = TaskRegistry.generate_job_id(
        task_type=TaskType.SEND_EMAIL,
        scheduler_type=SchedulerType.CRON,
        config_id=5
    )
    assert job_id == "email_cron_5"


def test_generate_job_id_once():
    """测试生成一次性任务的job_id"""
    job_id = TaskRegistry.generate_job_id(
        task_type=TaskType.BOT_SCRAPING,
        scheduler_type=SchedulerType.DATE,
        config_id=3
    )
    assert job_id == "scrape_bot_once_3"


def test_extract_config_id():
    """测试从job_id提取config_id"""
    config_id = TaskRegistry.extract_config_id_from_job_id("cleanup_tok_int_1")
    assert config_id == 1
    
    config_id = TaskRegistry.extract_config_id_from_job_id("email_cron_5")
    assert config_id == 5
    
    config_id = TaskRegistry.extract_config_id_from_job_id("scrape_bot_once_3")
    assert config_id == 3


def test_extract_config_id_invalid():
    """测试从无效job_id提取config_id"""
    config_id = TaskRegistry.extract_config_id_from_job_id("invalid_format")
    assert config_id is None
    
    config_id = TaskRegistry.extract_config_id_from_job_id("too_short")
    assert config_id is None
    
    config_id = TaskRegistry.extract_config_id_from_job_id("not_number_at_end_abc")
    assert config_id is None


def test_all_task_types_have_shortcuts():
    """确保所有任务类型都有缩写定义"""
    for task_type in TaskType:
        shortcut = TaskRegistry.get_task_type_shortcut(task_type)
        assert shortcut is not None
        assert len(shortcut) > 0


def test_all_scheduler_types_have_shortcuts():
    """确保所有调度类型都有缩写定义"""
    for scheduler_type in SchedulerType:
        shortcut = TaskRegistry.get_scheduler_type_shortcut(scheduler_type)
        assert shortcut is not None
        assert len(shortcut) > 0


def test_job_id_length_validation():
    """测试job_id长度验证"""
    # 正常情况应该通过
    job_id = TaskRegistry.generate_job_id(
        task_type=TaskType.CLEANUP_TOKENS,
        scheduler_type=SchedulerType.CRON,
        config_id=1
    )
    assert len(job_id) <= 50
    
    # 测试具有较长名称的任务类型
    job_id = TaskRegistry.generate_job_id(
        task_type=TaskType.SYSTEM_MONITOR,
        scheduler_type=SchedulerType.CRON,
        config_id=999999
    )
    assert len(job_id) <= 50


def test_job_id_uniqueness():
    """测试job_id的唯一性"""
    job_ids = set()
    
    # 生成多个不同的job_id，确保它们是唯一的
    for task_type in [TaskType.CLEANUP_TOKENS, TaskType.BOT_SCRAPING, TaskType.SEND_EMAIL]:
        for scheduler_type in [SchedulerType.CRON, SchedulerType.DATE]:
            for config_id in range(1, 4):
                job_id = TaskRegistry.generate_job_id(task_type, scheduler_type, config_id)
                assert job_id not in job_ids, f"重复的job_id: {job_id}"
                job_ids.add(job_id)


def test_task_type_shortcuts_consistency():
    """测试任务类型缩写的一致性"""
    for task_type in TaskType:
        shortcut = TaskRegistry.get_task_type_shortcut(task_type)
        # 缩写应该是小写字母和下划线
        assert shortcut.replace('_', '').isalnum()
        # 缩写不应该太长
        assert len(shortcut) <= 15


def test_scheduler_type_shortcuts_consistency():
    """测试调度类型缩写的一致性"""
    for scheduler_type in SchedulerType:
        shortcut = TaskRegistry.get_scheduler_type_shortcut(scheduler_type)
        # 缩写应该是小写字母
        assert shortcut.isalnum()
        # 缩写不应该太长
        assert len(shortcut) <= 8


def test_job_id_format_consistency():
    """测试job_id格式的一致性"""
    job_id = TaskRegistry.generate_job_id(
        task_type=TaskType.CLEANUP_TOKENS,
        scheduler_type=SchedulerType.CRON,
        config_id=123
    )
    
    parts = job_id.split('_')
    assert len(parts) >= 3
    
    # 最后一部分应该是数字
    assert parts[-1].isdigit()
    
    # 应该能够提取出原始的config_id
    extracted_id = TaskRegistry.extract_config_id_from_job_id(job_id)
    assert extracted_id == 123


def test_fallback_shortcuts():
    """测试缺少定义时的回退行为"""
    # 创建一个新的任务类型来测试回退行为
    class TestTaskType(TaskType):
        NEW_TASK = "new_test_task"
    
    # 对于未定义的任务类型，应该使用回退逻辑
    shortcut = TaskRegistry.get_task_type_shortcut(TestTaskType.NEW_TASK)
    assert shortcut is not None
    assert len(shortcut) > 0
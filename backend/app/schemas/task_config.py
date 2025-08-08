"""
任务配置相关的Pydantic模型
"""
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, Dict, Any, Union
from datetime import datetime

from app.core.task_type import TaskType, TaskStatus, SchedulerType


class TaskConfigBase(BaseModel):
    """任务配置基础模型"""
    name: str = Field(..., description="任务名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="任务描述", max_length=500)
    task_type: TaskType = Field(..., description="任务类型")
    scheduler_type: SchedulerType = Field(..., description="调度器类型")
    status: TaskStatus = Field(TaskStatus.ACTIVE, description="任务状态")
    parameters: Dict[str, Any] = Field({}, description="任务参数(JSON)")
    schedule_config: Dict[str, Any] = Field({}, description="调度配置(JSON)")
    max_retries: int = Field(0, description="最大重试次数", ge=0, le=10)
    timeout_seconds: Optional[int] = Field(None, description="任务超时时间(秒)", gt=0)
    priority: int = Field(5, description="任务优先级(1-10)", ge=1, le=10)


class TaskConfigCreate(TaskConfigBase):
    """创建任务配置"""
    
    @validator('parameters')
    def validate_parameters(cls, v, values):
        """验证任务参数"""
        task_type = values.get('task_type')
        if not task_type:
            return v
            
        # Bot爬取任务参数验证
        if task_type in [TaskType.BOT_SCRAPING, TaskType.MANUAL_SCRAPING, TaskType.BATCH_SCRAPING]:
            required_fields = ['bot_config_id']
            if task_type == TaskType.BOT_SCRAPING:
                required_fields.append('interval_hours')
            elif task_type == TaskType.BATCH_SCRAPING:
                required_fields = ['bot_config_ids']
                
            for field in required_fields:
                if field not in v:
                    raise ValueError(f'{task_type}任务缺少必要参数: {field}')
        
        # 清理任务参数验证  
        elif task_type in [TaskType.CLEANUP_CONTENT, TaskType.CLEANUP_EVENTS]:
            if 'days_old' not in v:
                raise ValueError(f'{task_type}任务缺少必要参数: days_old')
            if not isinstance(v['days_old'], int) or v['days_old'] <= 0:
                raise ValueError('days_old必须为正整数')
                
        return v
    
    @validator('schedule_config')
    def validate_schedule_config(cls, v, values):
        """验证调度配置"""
        scheduler_type = values.get('scheduler_type')
        if not scheduler_type:
            return v
            
        if scheduler_type == SchedulerType.INTERVAL:
            required = ['hours', 'minutes', 'seconds']
            if not any(k in v for k in required):
                raise ValueError('间隔调度至少需要指定hours、minutes或seconds中的一个')
                
        elif scheduler_type == SchedulerType.CRON:
            required = ['minute', 'hour', 'day', 'month', 'day_of_week']
            for field in required:
                if field not in v:
                    raise ValueError(f'Cron调度缺少必要参数: {field}')
                    
        elif scheduler_type == SchedulerType.DATE:
            if 'run_date' not in v:
                raise ValueError('日期调度缺少必要参数: run_date')
                
        return v


class TaskConfigUpdate(BaseModel):
    """更新任务配置"""
    name: Optional[str] = Field(None, description="任务名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="任务描述", max_length=500)
    status: Optional[TaskStatus] = Field(None, description="任务状态")
    parameters: Optional[Dict[str, Any]] = Field(None, description="任务参数(JSON)")
    schedule_config: Optional[Dict[str, Any]] = Field(None, description="调度配置(JSON)")
    max_retries: Optional[int] = Field(None, description="最大重试次数", ge=0, le=10)
    timeout_seconds: Optional[int] = Field(None, description="任务超时时间(秒)", gt=0)
    priority: Optional[int] = Field(None, description="任务优先级(1-10)", ge=1, le=10)


class TaskConfigResponse(TaskConfigBase):
    """任务配置响应"""
    id: int = Field(..., description="配置ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    
    model_config = ConfigDict(from_attributes=True)


class TaskConfigListResponse(BaseModel):
    """任务配置列表响应"""
    items: list[TaskConfigResponse] = Field(..., description="配置列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")


# === 特定任务类型的Schema ===

class BotScrapingTaskConfig(BaseModel):
    """Bot爬取任务配置"""
    bot_config_id: int = Field(..., description="Bot配置ID", gt=0)
    interval_hours: Optional[int] = Field(None, description="间隔小时数", gt=0, le=168)
    session_type: str = Field("auto", description="会话类型")


class BatchScrapingTaskConfig(BaseModel):
    """批量爬取任务配置"""
    bot_config_ids: list[int] = Field(..., description="Bot配置ID列表", min_items=1)
    session_type: str = Field("batch", description="会话类型")


class CleanupTaskConfig(BaseModel):
    """清理任务配置"""
    days_old: int = Field(..., description="清理天数", gt=0)
    cleanup_type: str = Field(..., description="清理类型")


class EmailTaskConfig(BaseModel):
    """邮件任务配置"""
    recipient_emails: list[str] = Field(..., description="收件人邮箱列表", min_items=1)
    subject: str = Field(..., description="邮件主题", min_length=1, max_length=200)
    template_name: str = Field(..., description="邮件模板名称")
    template_data: Dict[str, Any] = Field({}, description="模板数据")


class NotificationTaskConfig(BaseModel):
    """通知任务配置"""
    notification_type: str = Field(..., description="通知类型")  
    recipients: list[str] = Field(..., description="接收者列表", min_items=1)
    message: str = Field(..., description="通知消息", min_length=1, max_length=1000)
    urgency: str = Field("normal", description="紧急程度: low/normal/high")


# === 调度配置Schema ===

class IntervalScheduleConfig(BaseModel):
    """间隔调度配置"""
    weeks: Optional[int] = Field(None, ge=0)
    days: Optional[int] = Field(None, ge=0)
    hours: Optional[int] = Field(None, ge=0)
    minutes: Optional[int] = Field(None, ge=0)
    seconds: Optional[int] = Field(None, ge=0)
    start_date: Optional[datetime] = Field(None, description="开始时间")
    end_date: Optional[datetime] = Field(None, description="结束时间")


class CronScheduleConfig(BaseModel):
    """Cron调度配置"""
    minute: str = Field(..., description="分钟 (0-59)")
    hour: str = Field(..., description="小时 (0-23)")
    day: str = Field(..., description="日 (1-31)")
    month: str = Field(..., description="月 (1-12)")
    day_of_week: str = Field(..., description="周几 (0-6)")
    timezone: Optional[str] = Field("UTC", description="时区")
    start_date: Optional[datetime] = Field(None, description="开始时间")
    end_date: Optional[datetime] = Field(None, description="结束时间")


class DateScheduleConfig(BaseModel):
    """日期调度配置"""
    run_date: datetime = Field(..., description="执行时间")


# === 批量操作Schema ===

class BatchTaskConfigCreate(BaseModel):
    """批量创建任务配置"""
    configs: list[TaskConfigCreate] = Field(..., description="配置列表", min_items=1, max_items=100)


class BatchTaskConfigUpdate(BaseModel):
    """批量更新任务配置"""  
    config_ids: list[int] = Field(..., description="配置ID列表", min_items=1)
    updates: TaskConfigUpdate = Field(..., description="更新数据")


class TaskConfigQuery(BaseModel):
    """任务配置查询参数"""
    task_type: Optional[TaskType] = Field(None, description="任务类型")
    status: Optional[TaskStatus] = Field(None, description="任务状态")
    name_search: Optional[str] = Field(None, description="名称搜索", max_length=100)
    page: int = Field(1, description="页码", ge=1)
    page_size: int = Field(20, description="每页大小", ge=1, le=100)
    order_by: str = Field("created_at", description="排序字段")
    order_desc: bool = Field(True, description="降序排序")
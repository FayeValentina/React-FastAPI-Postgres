"""
任务配置相关的Pydantic模型
"""
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, Dict, Any, Union
from datetime import datetime

from app.constant.task_registry import TaskType, ConfigStatus, SchedulerType


class TaskConfigBase(BaseModel):
    """任务配置基础模型"""
    name: str = Field(..., description="任务名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="任务描述", max_length=500)
    task_type: TaskType = Field(..., description="任务类型")
    scheduler_type: SchedulerType = Field(..., description="调度器类型")
    status: ConfigStatus = Field(ConfigStatus.ACTIVE, description="任务状态")
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
        
        # 清理任务参数验证  
        if task_type in [TaskType.CLEANUP_CONTENT]:
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
            
        if scheduler_type == SchedulerType.CRON:
            # 支持两种cron格式
            has_cron_expression = 'cron_expression' in v
            required = ['minute', 'hour', 'day', 'month', 'day_of_week']
            has_cron_fields = all(field in v for field in required)
            
            if not has_cron_expression and not has_cron_fields:
                raise ValueError(f'Cron调度需要提供 cron_expression 或者完整的cron字段({", ".join(required)})')
                    
        elif scheduler_type == SchedulerType.DATE:
            if 'run_date' not in v:
                raise ValueError('日期调度缺少必要参数: run_date')
                
        return v


class TaskConfigUpdate(BaseModel):
    """更新任务配置"""
    name: Optional[str] = Field(None, description="任务名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="任务描述", max_length=500)
    status: Optional[ConfigStatus] = Field(None, description="任务状态")
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
    scheduler_status: Optional[str] = Field(None, description="调度器中的状态")
    stats: Optional[Dict[str, Any]] = Field(None, description="统计信息")
    model_config = ConfigDict(from_attributes=True)




class TaskConfigQuery(BaseModel):
    """任务配置查询参数"""
    task_type: Optional[TaskType] = Field(None, description="任务类型")
    status: Optional[ConfigStatus] = Field(None, description="任务状态")
    name_search: Optional[str] = Field(None, description="名称搜索", max_length=100)
    page: int = Field(1, description="页码", ge=1)
    page_size: int = Field(20, description="每页大小", ge=1, le=100)
    order_by: str = Field("created_at", description="排序字段")
    order_desc: bool = Field(True, description="降序排序")


class TaskConfigDeleteResponse(BaseModel):
    """任务配置删除响应"""
    success: bool = Field(..., description="删除是否成功")
    message: str = Field(..., description="删除结果消息")
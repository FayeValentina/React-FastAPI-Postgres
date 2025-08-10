from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from app.models.task_config import TaskConfig
from app.models.schedule_event import ScheduleEvent
from app.models.task_execution import TaskExecution
from app.schemas.task_config_schemas import TaskConfigCreate, TaskConfigUpdate, TaskConfigQuery
from app.utils.common import get_current_time
from app.core.task_registry import TaskType, TaskStatus, SchedulerType
from app.core.exceptions import (
    DatabaseError,
    ResourceNotFoundError,
    ValidationError
)


# 错误常量
ERROR_CREATE_TASK_CONFIG = "创建任务配置时出错"
ERROR_UPDATE_TASK_CONFIG = "更新任务配置时出错"
ERROR_DELETE_TASK_CONFIG = "删除任务配置时出错"
ERROR_TASK_CONFIG_NOT_FOUND = "任务配置不存在"


class CRUDTaskConfig:
    """任务配置CRUD操作"""
    
    async def get(self, db: AsyncSession, config_id: int) -> Optional[TaskConfig]:
        """获取指定ID的任务配置"""
        result = await db.execute(
            select(TaskConfig).filter(TaskConfig.id == config_id)
        )
        return result.scalar_one_or_none()
    
    async def get_with_relations(self, db: AsyncSession, config_id: int) -> Optional[TaskConfig]:
        """获取任务配置及其关联数据"""
        result = await db.execute(
            select(TaskConfig)
            .options(
                selectinload(TaskConfig.schedule_events),
                selectinload(TaskConfig.task_executions)
            )
            .filter(TaskConfig.id == config_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[TaskConfig]:
        """通过名称获取任务配置"""
        result = await db.execute(
            select(TaskConfig).filter(TaskConfig.name == name)
        )
        return result.scalar_one_or_none()
    
    async def get_multi(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> List[TaskConfig]:
        """获取多个任务配置"""
        result = await db.execute(
            select(TaskConfig)
            .offset(skip)
            .limit(limit)
            .order_by(TaskConfig.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_by_query(
        self,
        db: AsyncSession,
        query: TaskConfigQuery
    ) -> Tuple[List[TaskConfig], int]:
        """根据查询条件获取任务配置"""
        stmt = select(TaskConfig)
        count_stmt = select(func.count(TaskConfig.id))
        
        # 构建过滤条件
        filters = []
        
        if query.task_type:
            filters.append(TaskConfig.task_type == query.task_type)
        
        if query.status:
            filters.append(TaskConfig.status == query.status)
        
        if query.name_search:
            filters.append(
                TaskConfig.name.ilike(f"%{query.name_search}%")
            )
        
        if filters:
            stmt = stmt.filter(and_(*filters))
            count_stmt = count_stmt.filter(and_(*filters))
        
        # 排序
        if query.order_by == "name":
            order_field = TaskConfig.name
        elif query.order_by == "updated_at":
            order_field = TaskConfig.updated_at
        else:
            order_field = TaskConfig.created_at
        
        if query.order_desc:
            order_field = order_field.desc()
        
        stmt = stmt.order_by(order_field)
        
        # 分页
        offset = (query.page - 1) * query.page_size
        stmt = stmt.offset(offset).limit(query.page_size)
        
        # 执行查询
        result = await db.execute(stmt)
        configs = result.scalars().all()
        
        count_result = await db.execute(count_stmt)
        total = count_result.scalar()
        
        return configs, total
    
    async def get_by_type(
        self,
        db: AsyncSession,
        task_type: TaskType,
        status: Optional[TaskStatus] = None
    ) -> List[TaskConfig]:
        """根据任务类型获取配置"""
        filters = [TaskConfig.task_type == task_type]
        
        if status:
            filters.append(TaskConfig.status == status)
        
        result = await db.execute(
            select(TaskConfig)
            .filter(and_(*filters))
            .order_by(TaskConfig.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_active_configs(self, db: AsyncSession) -> List[TaskConfig]:
        """获取所有活跃的任务配置"""
        result = await db.execute(
            select(TaskConfig)
            .filter(TaskConfig.status == TaskStatus.ACTIVE)
            .order_by(TaskConfig.priority.desc(), TaskConfig.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_scheduled_configs(self, db: AsyncSession) -> List[TaskConfig]:
        """获取所有需要调度的任务配置"""
        result = await db.execute(
            select(TaskConfig)
            .filter(
                and_(
                    TaskConfig.status == TaskStatus.ACTIVE,
                    TaskConfig.scheduler_type != SchedulerType.MANUAL
                )
            )
            .order_by(TaskConfig.priority.desc(), TaskConfig.created_at.desc())
        )
        return result.scalars().all()
    
    async def create(self, db: AsyncSession, obj_in: TaskConfigCreate) -> TaskConfig:
        """创建任务配置"""
        try:
            db_obj = TaskConfig(
                name=obj_in.name,
                description=obj_in.description,
                task_type=obj_in.task_type,
                scheduler_type=obj_in.scheduler_type,
                status=obj_in.status,
                parameters=obj_in.parameters,
                schedule_config=obj_in.schedule_config,
                max_retries=obj_in.max_retries,
                timeout_seconds=obj_in.timeout_seconds,
                priority=obj_in.priority
            )
            
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"{ERROR_CREATE_TASK_CONFIG}: {str(e)}")
    
    async def update(
        self,
        db: AsyncSession,
        db_obj: TaskConfig,
        obj_in: TaskConfigUpdate
    ) -> TaskConfig:
        """更新任务配置"""
        try:
            update_data = obj_in.model_dump(exclude_unset=True)
            
            if update_data:
                update_data["updated_at"] = get_current_time()
                
                stmt = (
                    update(TaskConfig)
                    .where(TaskConfig.id == db_obj.id)
                    .values(**update_data)
                    .returning(TaskConfig)
                )
                
                result = await db.execute(stmt)
                await db.commit()
                updated_obj = result.scalar_one()
                
                return updated_obj
            
            return db_obj
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"{ERROR_UPDATE_TASK_CONFIG}: {str(e)}")
    
    async def delete(self, db: AsyncSession, config_id: int) -> bool:
        """删除任务配置"""
        try:
            # 删除关联的调度事件和执行记录会通过级联删除自动处理
            result = await db.execute(
                delete(TaskConfig).where(TaskConfig.id == config_id)
            )
            await db.commit()
            
            return result.rowcount > 0
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"{ERROR_DELETE_TASK_CONFIG}: {str(e)}")
    
    async def batch_update_status(
        self,
        db: AsyncSession,
        config_ids: List[int],
        status: TaskStatus
    ) -> int:
        """批量更新任务状态"""
        try:
            result = await db.execute(
                update(TaskConfig)
                .where(TaskConfig.id.in_(config_ids))
                .values(status=status, updated_at=get_current_time())
            )
            await db.commit()
            return result.rowcount
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"批量更新任务状态时出错: {str(e)}")
    
    async def update_parameters(
        self,
        db: AsyncSession,
        config_id: int,
        parameters: Dict[str, Any]
    ) -> TaskConfig:
        """更新任务参数"""
        try:
            stmt = (
                update(TaskConfig)
                .where(TaskConfig.id == config_id)
                .values(parameters=parameters, updated_at=get_current_time())
                .returning(TaskConfig)
            )
            
            result = await db.execute(stmt)
            await db.commit()
            return result.scalar_one()
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"更新任务参数时出错: {str(e)}")
    
    async def update_schedule_config(
        self,
        db: AsyncSession,
        config_id: int,
        schedule_config: Dict[str, Any]
    ) -> TaskConfig:
        """更新调度配置"""
        try:
            stmt = (
                update(TaskConfig)
                .where(TaskConfig.id == config_id)
                .values(schedule_config=schedule_config, updated_at=get_current_time())
                .returning(TaskConfig)
            )
            
            result = await db.execute(stmt)
            await db.commit()
            return result.scalar_one()
            
        except Exception as e:
            await db.rollback()
            raise DatabaseError(f"更新调度配置时出错: {str(e)}")
    
    async def get_execution_stats(
        self,
        db: AsyncSession,
        config_id: int
    ) -> Dict[str, Any]:
        """获取任务执行统计信息"""
        # 总执行次数
        total_result = await db.execute(
            select(func.count(TaskExecution.id))
            .filter(TaskExecution.task_config_id == config_id)
        )
        total_runs = total_result.scalar() or 0
        
        if total_runs == 0:
            return {
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "last_run": None,
                "last_status": None
            }
        
        # 成功/失败次数
        success_result = await db.execute(
            select(func.count(TaskExecution.id))
            .filter(
                and_(
                    TaskExecution.task_config_id == config_id,
                    TaskExecution.status == "success"
                )
            )
        )
        successful_runs = success_result.scalar() or 0
        failed_runs = total_runs - successful_runs
        
        # 平均执行时间
        avg_result = await db.execute(
            select(func.avg(TaskExecution.duration_seconds))
            .filter(
                and_(
                    TaskExecution.task_config_id == config_id,
                    TaskExecution.duration_seconds.isnot(None)
                )
            )
        )
        avg_duration = float(avg_result.scalar() or 0.0)
        
        # 最后执行信息
        last_result = await db.execute(
            select(TaskExecution.completed_at, TaskExecution.status)
            .filter(TaskExecution.task_config_id == config_id)
            .order_by(TaskExecution.created_at.desc())
            .limit(1)
        )
        last_execution = last_result.first()
        
        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "success_rate": (successful_runs / total_runs * 100) if total_runs > 0 else 0.0,
            "avg_duration": avg_duration,
            "last_run": last_execution[0].isoformat() if last_execution and last_execution[0] else None,
            "last_status": last_execution[1] if last_execution else None
        }
    
    async def count_by_type(self, db: AsyncSession) -> Dict[TaskType, int]:
        """按类型统计任务配置数量"""
        result = await db.execute(
            select(TaskConfig.task_type, func.count(TaskConfig.id))
            .group_by(TaskConfig.task_type)
        )
        
        return {task_type: count for task_type, count in result.all()}
    
    async def count_by_status(self, db: AsyncSession) -> Dict[TaskStatus, int]:
        """按状态统计任务配置数量"""
        result = await db.execute(
            select(TaskConfig.status, func.count(TaskConfig.id))
            .group_by(TaskConfig.status)
        )
        
        return {status: count for status, count in result.all()}
    
    async def get_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """获取任务配置统计信息"""
        try:
            # 总配置数
            total_result = await db.execute(
                select(func.count(TaskConfig.id))
            )
            total_configs = total_result.scalar() or 0
            
            # 活跃配置数
            active_result = await db.execute(
                select(func.count(TaskConfig.id))
                .filter(TaskConfig.status == TaskStatus.ACTIVE)
            )
            active_configs = active_result.scalar() or 0
            
            # 按类型统计
            type_stats = await self.count_by_type(db)
            
            # 按状态统计
            status_stats = await self.count_by_status(db)
            
            return {
                "total_configs": total_configs,
                "active_configs": active_configs,
                "by_type": {str(k): v for k, v in type_stats.items()},
                "by_status": {str(k): v for k, v in status_stats.items()}
            }
            
        except Exception as e:
            raise DatabaseError(f"获取统计信息失败: {str(e)}")


# 全局CRUD实例
crud_task_config = CRUDTaskConfig()
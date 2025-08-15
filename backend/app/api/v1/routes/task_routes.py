"""Task management API routes using TaskManager service."""

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Path
from typing import Annotated, Any, Dict, List, Optional
from datetime import datetime

from app.models.user import User
from app.dependencies.current_user import get_current_superuser, get_current_active_user
from app.schemas.task_config_schemas import (
    TaskConfigCreate, 
    TaskConfigUpdate, 
    TaskConfigResponse,
    TaskConfigQuery,
    TaskConfigDeleteResponse
)
from app.schemas.job_schemas import (
    SystemStatusResponse,
    HealthCheckResponse,
    OperationResponse,
    TaskExecutionResult,
    BatchCreateResponse,
    BatchDeleteResponse,
    BatchExecutionResponse,
    TaskRevokeResponse,
    BatchRevokeResponse,
    QueueStatsResponse,
    QueueLengthResponse,
    TaskTypeSupportResponse,
    EnumValuesResponse,
    ValidationResponse,
    TaskStatusResponse,
    ActiveTaskInfo,
    ScheduledJobInfo,
    ScheduleActionResponse
)
from app.core.task_manager import task_manager
from app.core.task_registry import TaskType, ConfigStatus, SchedulerType, ScheduleAction, TaskRegistry
from app.db.base import AsyncSessionLocal
from app.crud.task_config import crud_task_config
from app.crud.task_execution import crud_task_execution
from app.crud.schedule_event import crud_schedule_event


router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# System Management Endpoints
# ---------------------------------------------------------------------------

@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status(
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> Dict[str, Any]:
    """
    Get comprehensive system status including scheduler, broker, and configuration statistics.
    
    Returns:
        System status with scheduler state, task counts, and configuration statistics
    """
    return await task_manager.get_system_status()


@router.get("/system/health", response_model=HealthCheckResponse)
async def get_system_health(
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> Dict[str, Any]:
    """
    Get system health check status.
    
    Returns:
        Health status of all system components
    """
    status = await task_manager.get_system_status()
    
    is_healthy = (
        status.get("scheduler_running", False) and 
        status.get("broker_connected", False)
    )
    
    return {
        "status": "healthy" if is_healthy else "degraded",
        "scheduler_running": status.get("scheduler_running", False),
        "broker_connected": status.get("broker_connected", False),
        "total_scheduled_jobs": status.get("total_scheduled_jobs", 0),
        "total_active_tasks": status.get("total_active_tasks", 0),
        "timestamp": status.get("timestamp")
    }


# ---------------------------------------------------------------------------
# Task Configuration CRUD Endpoints
# ---------------------------------------------------------------------------

@router.get("/configs", response_model=List[TaskConfigResponse])
async def list_task_configs(
    task_type: Optional[str] = Query(None, description="Filter by task type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    name_search: Optional[str] = Query(None, description="Search by name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> List[Dict[str, Any]]:
    """
    List task configurations with filtering and pagination.
    
    Query Parameters:
        - task_type: Filter by TaskType enum value
        - status: Filter by ConfigStatus enum value
        - name_search: Search configurations by name
        - page: Page number for pagination
        - page_size: Number of items per page
    """
    configs = await task_manager.list_task_configs(
        task_type=task_type,
        status=status
    )
    
    # Apply name search if provided
    if name_search:
        configs = [c for c in configs if name_search.lower() in c.get("name", "").lower()]
    
    # Apply pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_configs = configs[start_idx:end_idx]
    
    return paginated_configs


@router.get("/configs/{config_id}", response_model=TaskConfigResponse)
async def get_task_config(
    config_id: int = Path(..., description="Task configuration ID"),
    include_stats: bool = Query(False, description="Include execution statistics"),
    verify_scheduler_status: bool = Query(False, description="Verify status against scheduler"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Get detailed information about a specific task configuration.
    
    Parameters:
        - config_id: Task configuration ID
        - include_stats: Whether to include execution statistics
        - verify_scheduler_status: Whether to verify status against scheduler
    """
    config = await task_manager.get_task_config(config_id, verify_scheduler_status)
    if not config:
        raise HTTPException(status_code=404, detail="Task configuration not found")
    
    # Optionally add execution statistics
    if include_stats:
        async with AsyncSessionLocal() as db:
            stats = await crud_task_config.get_execution_stats(db, config_id)
            config["stats"] = stats
    
    return config


@router.post("/configs", response_model=TaskConfigResponse, status_code=201)
async def create_task_config(
    config: TaskConfigCreate,
    auto_start: bool = Query(False, description="Automatically start scheduling after creation"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Create a new task configuration.
    
    Parameters:
        - config: Task configuration data
        - auto_start: Whether to automatically start scheduling
    """
    try:
        # Set status based on auto_start
        config_dict = config.dict()
        if auto_start and config.scheduler_type != SchedulerType.MANUAL:
            config_dict["status"] = ConfigStatus.ACTIVE
        
        config_id = await task_manager.create_task_config(**config_dict)
        if config_id is None:
            raise HTTPException(status_code=400, detail="Failed to create task configuration")
        
        # Return the created configuration
        created_config = await task_manager.get_task_config(config_id)
        return created_config or {"id": config_id}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.put("/configs/{config_id}", response_model=TaskConfigResponse)
async def update_task_config(
    config_id: int = Path(..., description="Task configuration ID"),
    updates: TaskConfigUpdate = Body(..., description="Update data"),
    reload_schedule: bool = Query(True, description="Reload schedule if task is scheduled"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    更新任务配置（支持部分更新）
    
    Parameters:
        - config_id: Task configuration ID
        - updates: Fields to update (只需提供要更新的字段)
        - reload_schedule: Whether to reload the schedule if the task is scheduled
    """
    success = await task_manager.update_task_config(
        config_id, updates.dict(exclude_unset=True)  # exclude_unset支持部分更新
    )
    if not success:
        raise HTTPException(status_code=404, detail="Task configuration not found")
    
    # Return updated configuration
    updated_config = await task_manager.get_task_config(config_id)
    return updated_config or {"id": config_id, "updated": True}


@router.delete("/configs/{config_id}", response_model=TaskConfigDeleteResponse)
async def delete_task_config(
    config_id: int = Path(..., description="Task configuration ID"),
    force: bool = Query(False, description="Force delete even if task is running"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Delete a task configuration.
    
    Parameters:
        - config_id: Task configuration ID
        - force: Force deletion even if task is currently scheduled or running
    """
    # Check if task is running if not forcing
    if not force:
        active_tasks = await task_manager.list_active_tasks()
        if any(t["config_id"] == config_id for t in active_tasks):
            raise HTTPException(
                status_code=400, 
                detail="Task is currently running. Use force=true to delete anyway."
            )
    
    success = await task_manager.delete_task_config(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task configuration not found")
    
    return {"success": True, "message": f"Task configuration {config_id} deleted"}


# ---------------------------------------------------------------------------
# Batch Operations (Unified)
# ---------------------------------------------------------------------------

@router.post("/batch-operations", response_model=Dict[str, Any])
async def batch_operations(
    operation: str = Body(..., description="Operation type: delete, execute, revoke, execute-by-type"),
    config_ids: Optional[List[int]] = Body(None, description="Config IDs for delete/execute"),
    task_ids: Optional[List[str]] = Body(None, description="Task IDs for revoke"),
    task_type: Optional[str] = Body(None, description="Task type for execute-by-type"),
    options: Optional[Dict[str, Any]] = Body(default={}, description="Additional options"),
    page_size: Optional[int] = Body(1000, description="Page size for execute-by-type"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    统一的批量操作端点
    
    Operations:
        - delete: 批量删除配置（需要 config_ids）
        - execute: 批量执行任务（需要 config_ids）
        - revoke: 批量撤销任务（需要 task_ids）
        - execute-by-type: 批量执行指定类型的所有活跃配置（需要 task_type）
    
    Parameters:
        - operation: Operation type
        - config_ids: Configuration IDs for delete/execute operations
        - task_ids: Task IDs for revoke operation
        - task_type: Task type for execute-by-type operation
        - options: Additional options specific to each operation
    """
    operation = operation.lower()
    
    if operation == "delete":
        if not config_ids:
            raise HTTPException(status_code=400, detail="config_ids required for delete operation")
        
        deleted = []
        failed = []
        
        for config_id in config_ids:
            try:
                success = await task_manager.delete_task_config(config_id)
                if success:
                    deleted.append(config_id)
                else:
                    failed.append({"id": config_id, "error": "Not found"})
            except Exception as e:
                failed.append({"id": config_id, "error": str(e)})
        
        return {
            "operation": "delete",
            "deleted": deleted,
            "failed": failed,
            "total_deleted": len(deleted),
            "total_failed": len(failed)
        }
    
    elif operation == "execute":
        if not config_ids:
            raise HTTPException(status_code=400, detail="config_ids required for execute operation")
        
        task_ids_result = []
        failed = []
        
        for config_id in config_ids:
            try:
                task_id = await task_manager.execute_task_immediately(config_id, **options)
                if task_id:
                    task_ids_result.append(task_id)
                else:
                    failed.append({"id": config_id, "error": "Failed to execute"})
            except Exception as e:
                failed.append({"id": config_id, "error": str(e)})
        
        return {
            "operation": "execute",
            "task_ids": task_ids_result,
            "failed": failed,
            "total_submitted": len(task_ids_result),
            "total_failed": len(failed),
            "config_ids": config_ids,
            "status": "submitted"
        }
    
    elif operation == "revoke":
        if not task_ids:
            raise HTTPException(status_code=400, detail="task_ids required for revoke operation")
        
        results = []
        terminate = options.get("terminate", False)
        
        for task_id in task_ids:
            try:
                # Use the single revoke logic from existing endpoint
                async with AsyncSessionLocal() as db:
                    execution = await crud_task_execution.get_by_task_id(db, task_id)
                    if execution and execution.status == "running":
                        await crud_task_execution.update_status(
                            db=db,
                            execution_id=execution.id,
                            status="failed",
                            completed_at=datetime.utcnow(),
                            error_message="Task revoked by user"
                        )
                        
                        results.append({
                            "task_id": task_id, 
                            "revoked": True, 
                            "message": "Task marked as revoked"
                        })
                    else:
                        results.append({
                            "task_id": task_id, 
                            "revoked": False, 
                            "message": "Task not found or not running"
                        })
            except Exception as e:
                results.append({
                    "task_id": task_id,
                    "revoked": False,
                    "message": str(e)
                })
        
        successful = [r for r in results if r.get("revoked")]
        failed_results = [r for r in results if not r.get("revoked")]
        
        return {
            "operation": "revoke",
            "total_revoked": len(successful),
            "total_failed": len(failed_results),
            "results": results
        }
    
    elif operation == "execute-by-type":
        if not task_type:
            raise HTTPException(status_code=400, detail="task_type required for execute-by-type operation")
        
        # Get all active configs of this type
        configs = await task_manager.list_task_configs(
            task_type=task_type,
            status=ConfigStatus.ACTIVE.value,
            page_size=page_size
        )
        
        task_ids_result = []
        failed = []
        
        for config in configs:
            try:
                task_id = await task_manager.execute_task_immediately(config["id"], **options)
                if task_id:
                    task_ids_result.append(task_id)
                else:
                    failed.append({"id": config["id"], "error": "Failed to execute"})
            except Exception as e:
                failed.append({"id": config["id"], "error": str(e)})
        
        return {
            "operation": "execute-by-type",
            "task_ids": task_ids_result,
            "failed": failed,
            "total_submitted": len(task_ids_result),
            "total_failed": len(failed),
            "task_type": task_type,
            "status": "submitted"
        }
    
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid operation: {operation}. Supported operations: delete, execute, revoke, execute-by-type"
        )


# ---------------------------------------------------------------------------
# Scheduling Operations
# ---------------------------------------------------------------------------

@router.post("/configs/{config_id}/schedule", response_model=ScheduleActionResponse)
async def manage_scheduled_task(
    config_id: int = Path(..., description="Task configuration ID"),
    action: str = Query(..., description="Schedule action: start, stop, pause, resume, reload"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Unified task schedule management endpoint.
    
    Supported actions:
    - start: Start task scheduling (status -> active)
    - stop: Stop task scheduling (status -> inactive)  
    - pause: Pause task scheduling (status -> paused)
    - resume: Resume task scheduling (status -> active)
    - reload: Reload task scheduling (status -> active)
    
    On failure, status will be set to error
    
    Parameters:
        - config_id: Task configuration ID
        - action: Schedule action type (query parameter)
    
    Example:
        POST /configs/205/schedule?action=pause
    """
    try:
        # Validate action type
        action_value = action.lower()
        if action_value not in [e.value for e in ScheduleAction]:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported action: {action_value}. Supported: {[e.value for e in ScheduleAction]}"
            )
        
        # Execute action through task manager
        result = await task_manager.manage_scheduled_task(config_id, action_value)
        
        if not result["success"]:
            raise HTTPException(
                status_code=400, 
                detail=result["message"]
            )
        
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid action: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")


@router.get("/scheduled", response_model=List[ScheduledJobInfo])
async def get_scheduled_jobs(
    include_paused: bool = Query(True, description="Include paused jobs"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> List[Dict[str, Any]]:
    """
    Get all currently scheduled jobs.
    
    Parameters:
        - include_paused: Whether to include paused jobs in the result
    """
    from app.scheduler import get_scheduled_tasks
    
    tasks = await get_scheduled_tasks()
    
    # Convert to response format
    jobs = []
    for task in tasks:
        job_info = {
            "id": task.get("task_id", ""),
            "name": task.get("task_name", ""),
            "next_run_time": task.get("next_run"),
            "trigger": str(task.get("schedule", "")),
            "pending": task.get("next_run") is not None,
            "func": task.get("task_name"),
            "args": [],
            "kwargs": {}
        }
        
        # Filter out paused jobs if requested
        if not include_paused and not job_info["pending"]:
            continue
            
        jobs.append(job_info)
    
    return jobs


# ---------------------------------------------------------------------------
# Task Execution
# ---------------------------------------------------------------------------

@router.post("/configs/{config_id}/execute", response_model=TaskExecutionResult)
async def execute_task_immediately(
    config_id: int = Path(..., description="Task configuration ID"),
    options: Dict[str, Any] = Body(default={}, description="Execution options"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Execute a task configuration immediately.
    
    Parameters:
        - config_id: Task configuration ID
        - options: Execution options (additional parameters)
    """
    task_id = await task_manager.execute_task_immediately(config_id, **options)
    if not task_id:
        raise HTTPException(status_code=400, detail="Failed to execute task")
    
    return {
        "task_id": task_id,
        "config_id": config_id,
        "status": "submitted",
        "message": f"Task {config_id} submitted for execution"
    }


@router.post("/execute/by-type", response_model=TaskExecutionResult)
async def execute_task_by_type(
    task_type: str = Body(..., description="Task type"),
    task_params: Dict[str, Any] = Body(default={}, description="Task parameters"),
    queue: str = Body(default="default", description="Queue name"),
    options: Dict[str, Any] = Body(default={}, description="Execution options"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Execute a task directly by type without configuration.
    
    Parameters:
        - task_type: TaskType enum value
        - task_params: Parameters for the task
        - queue: Queue to submit the task to
        - options: Additional execution options
    """
    # Validate task type
    try:
        task_type_enum = TaskType(task_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported task type: {task_type}")
    
    # Get task function
    from app.core.task_registry import get_task_function
    task_func = get_task_function(task_type_enum)
    
    if not task_func:
        raise HTTPException(status_code=400, detail=f"Task type {task_type} not implemented")
    
    # Execute task directly
    try:
        # Add config_id=None for direct execution if not provided
        task_params_with_defaults = {
            "config_id": None,  # Default for direct execution
            **task_params  # User params override defaults
        }
        task = await task_func.kiq(**task_params_with_defaults, **options)
        
        # Create a task execution record
        async with AsyncSessionLocal() as db:
            await crud_task_execution.create(
                db=db,
                config_id=None,  # No config for direct execution
                task_id=task.task_id,
                status="running",
                started_at=datetime.utcnow(),
            )

        return {
            "task_id": task.task_id,
            "task_type": task_type,
            "status": "submitted",
            "queue": queue
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute task: {str(e)}")






# ---------------------------------------------------------------------------
# Task and Queue Status
# ---------------------------------------------------------------------------

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str = Path(..., description="Task ID"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Get the current status of a task.
    
    Parameters:
        - task_id: Task ID (UUID format)
    """
    status = await task_manager.get_task_status(task_id)
    
    return {
        "task_id": task_id,
        "status": status.get("status", "unknown"),
        "result": status.get("result"),
        "traceback": status.get("error"),
        "name": None,  # Can be added if needed
        "args": [],
        "kwargs": {}
    }


@router.get("/active", response_model=List[ActiveTaskInfo])
async def get_active_tasks(
    queue: Optional[str] = Query(None, description="Filter by queue name"),
    worker: Optional[str] = Query(None, description="Filter by worker name"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> List[Dict[str, Any]]:
    """
    Get all currently active tasks.
    
    Parameters:
        - queue: Optional queue name filter
        - worker: Optional worker name filter
    """
    tasks = await task_manager.list_active_tasks()
    
    # Convert to response format and apply filters
    active_tasks = []
    for t in tasks:
        task_queue = t.get("queue", "default")
        
        # Apply queue filter if specified
        if queue and task_queue != queue:
            continue
            
        task_info = {
            "task_id": t["task_id"],
            "name": f"Task Config {t['config_id']} ({t.get('task_type', 'unknown')})",
            "args": [],
            "kwargs": {},
            "worker": worker,  # Can be populated if available from TaskIQ
            "queue": task_queue
        }
        active_tasks.append(task_info)
    
    return active_tasks


@router.get("/queues", response_model=QueueStatsResponse)
async def get_queue_stats(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Get statistics for all queues with actual task distribution."""
    queues = ["default", "cleanup", "scraping", "high_priority", "low_priority"]
    stats = {}
    
    # Initialize all queues with 0 count
    for queue_name in queues:
        stats[queue_name] = {
            "length": 0,
            "status": "active"
        }
    
    # Get active tasks with queue information
    active_tasks = await task_manager.list_active_tasks()
    
    # Count tasks by queue
    for task in active_tasks:
        queue_name = task.get("queue", "default")
        
        # Ensure the queue exists in our stats
        if queue_name not in stats:
            stats[queue_name] = {
                "length": 0,
                "status": "active"
            }
        
        stats[queue_name]["length"] += 1
    
    return {
        "queues": stats,
        "total_tasks": len(active_tasks)
    }

@router.post("/revoke/{task_id}", response_model=TaskRevokeResponse)
async def revoke_task(
    task_id: str = Path(..., description="Task ID"),
    terminate: bool = Query(False, description="Terminate the task if running"),
    signal: str = Query("TERM", description="Signal to send (TERM or KILL)"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Revoke a task (TaskIQ doesn't support direct revocation).
    
    Parameters:
        - task_id: Task ID
        - terminate: Whether to terminate if the task is currently executing
        - signal: Signal type (TERM for graceful, KILL for force)
    """
    # TaskIQ doesn't have direct task revoke functionality
    # Mark task as failed in database
    async with AsyncSessionLocal() as db:
        execution = await crud_task_execution.get_by_task_id(db, task_id)
        if execution and execution.status == "running":
            await crud_task_execution.update_status(
                db=db,
                execution_id=execution.id,
                status="failed",
                completed_at=datetime.utcnow(),
                error_message="Task revoked by user"
            )
            
            return {
                "task_id": task_id, 
                "revoked": True, 
                "message": "Task marked as revoked"
            }
    
    return {
        "task_id": task_id, 
        "revoked": False, 
        "message": "Task not found or not running"
    }




# ---------------------------------------------------------------------------
# Utility Endpoints
# ---------------------------------------------------------------------------

@router.get("/enums", response_model=EnumValuesResponse)
async def get_enum_values(
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
) -> Dict[str, Any]:
    """
    获取所有可用的枚举值和支持的任务类型
    
    Useful for frontend dropdowns and validation.
    """
    from app.core.task_registry import get_task_function
    
    # 获取支持的任务类型及其实现状态
    task_types_list: List[Dict[str, Any]] = []
    for task_type in TaskType:
        task_func = get_task_function(task_type)
        # 将每个任务的详细信息作为一个字典追加到列表中
        task_types_list.append({
            "name": task_type.value,
            "description": f"Task type for {task_type.value.replace('_', ' ').title()}",
            "implemented": task_func is not None
        })
    
    return {
        "task_types": task_types_list,  # 包含描述和实现状态
        "task_statuses": [s.value for s in ConfigStatus],
        "scheduler_types": [s.value for s in SchedulerType]
    }

# ---------------------------------------------------------------------------
# Statistics and Reports Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats")
async def get_statistics(
    type: str = Query(..., description="Stats type: executions or events"),
    config_id: Optional[int] = Query(None, description="Filter by configuration ID"),
    days: int = Query(7, ge=1, le=365, description="Number of days to include"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    获取统计数据
    
    Parameters:
        - type: 统计类型（executions 或 events）
        - config_id: 可选的配置ID过滤
        - days: 统计天数
    """
    async with AsyncSessionLocal() as db:
        if type == "executions":
            if config_id:
                stats = await crud_task_execution.get_stats_by_config(db, config_id, days)
            else:
                stats = await crud_task_execution.get_global_stats(db, days)
        elif type == "events":
            if config_id:
                stats = await crud_schedule_event.get_stats_by_config(db, config_id, days)
            else:
                stats = await crud_schedule_event.get_global_stats(db, days)
        else:
            raise HTTPException(status_code=400, detail="Invalid stats type")
        
        return stats
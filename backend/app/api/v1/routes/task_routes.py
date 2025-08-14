"""Task management API routes using TaskManager service."""

from fastapi import APIRouter, Depends, HTTPException, Body, Query, Path
from typing import Annotated, Any, Dict, List, Optional

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
    Update an existing task configuration.
    
    Parameters:
        - config_id: Task configuration ID
        - updates: Fields to update
        - reload_schedule: Whether to reload the schedule if the task is scheduled
    """
    success = await task_manager.update_task_config(
        config_id, updates.dict(exclude_unset=True)
    )
    if not success:
        raise HTTPException(status_code=404, detail="Task configuration not found")
    
    # Return updated configuration
    updated_config = await task_manager.get_task_config(config_id)
    return updated_config or {"id": config_id, "updated": True}


@router.patch("/configs/{config_id}", response_model=TaskConfigResponse)
async def patch_task_config(
    config_id: int = Path(..., description="Task configuration ID"),
    updates: Dict[str, Any] = Body(..., description="Partial update data"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Partially update a task configuration (PATCH method).
    
    Allows updating individual fields without providing the full configuration.
    """
    success = await task_manager.update_task_config(config_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Task configuration not found")
    
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
# Batch Configuration Operations
# ---------------------------------------------------------------------------

@router.post("/configs/batch", response_model=BatchCreateResponse)
async def batch_create_configs(
    configs: List[TaskConfigCreate] = Body(..., description="List of configurations to create"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Create multiple task configurations in batch.
    
    Parameters:
        - configs: List of task configurations to create
    """
    created_ids = []
    failed = []
    
    for idx, config in enumerate(configs):
        try:
            config_id = await task_manager.create_task_config(**config.dict())
            if config_id:
                created_ids.append(config_id)
            else:
                failed.append({"index": idx, "error": "Creation failed"})
        except Exception as e:
            failed.append({"index": idx, "error": str(e)})
    
    return {
        "created": created_ids,
        "failed": failed,
        "total_created": len(created_ids),
        "total_failed": len(failed)
    }


@router.delete("/configs/batch", response_model=BatchDeleteResponse)
async def batch_delete_configs(
    config_ids: List[int] = Body(..., description="List of configuration IDs to delete"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Delete multiple task configurations in batch.
    
    Parameters:
        - config_ids: List of configuration IDs to delete
    """
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
        "deleted": deleted,
        "failed": failed,
        "total_deleted": len(deleted),
        "total_failed": len(failed)
    }


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
    from app.scheduler import get_task_function
    task_func = get_task_function(task_type_enum)
    
    if not task_func:
        raise HTTPException(status_code=400, detail=f"Task type {task_type} not implemented")
    
    # Execute task directly
    try:
        task = await task_func.kiq(**task_params, **options)
        
        return {
            "task_id": task.task_id,
            "task_type": task_type,
            "status": "submitted",
            "queue": queue
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute task: {str(e)}")


@router.post("/execute/batch", response_model=BatchExecutionResponse)
async def execute_multiple_configs(
    config_ids: List[int] = Body(..., description="List of configuration IDs to execute"),
    options: Dict[str, Any] = Body(default={}, description="Execution options"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Execute multiple task configurations in batch.
    
    Parameters:
        - config_ids: List of configuration IDs
        - options: Execution options for all tasks
    """
    task_ids = []
    
    for config_id in config_ids:
        try:
            task_id = await task_manager.execute_task_immediately(config_id, **options)
            if task_id:
                task_ids.append(task_id)
        except Exception:
            # Continue with other tasks even if one fails
            pass
    
    return {
        "task_ids": task_ids,
        "total_submitted": len(task_ids),
        "config_ids": config_ids,
        "status": "submitted"
    }


@router.post("/execute/batch-by-type", response_model=BatchExecutionResponse)
async def execute_batch_by_task_type(
    task_type: str = Body(..., description="Task type"),
    options: Dict[str, Any] = Body(default={}, description="Execution options"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Execute all active task configurations of a specific type.
    
    Parameters:
        - task_type: TaskType enum value
        - options: Execution options for all tasks
    """
    # Get all active configs of this type
    configs = await task_manager.list_task_configs(
        task_type=task_type,
        status=ConfigStatus.ACTIVE.value
    )
    
    task_ids = []
    for config in configs:
        try:
            task_id = await task_manager.execute_task_immediately(config["id"], **options)
            if task_id:
                task_ids.append(task_id)
        except Exception:
            pass
    
    return {
        "task_ids": task_ids,
        "total_submitted": len(task_ids),
        "task_type": task_type,
        "status": "submitted"
    }


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
    
    # Convert to response format
    active_tasks = []
    for t in tasks:
        task_info = {
            "task_id": t["task_id"],
            "name": f"Task Config {t['config_id']}",
            "args": [],
            "kwargs": {},
            "worker": worker,  # Can be populated if available
            "queue": queue or "default"
        }
        active_tasks.append(task_info)
    
    return active_tasks


@router.get("/queues", response_model=QueueStatsResponse)
async def get_queue_stats(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Get statistics for all queues."""
    queues = ["default", "cleanup", "scraping", "high_priority", "low_priority"]
    stats = {}
    
    # Get active tasks count
    active_tasks = await task_manager.list_active_tasks()
    
    for queue_name in queues:
        # Simplified stats since TaskIQ doesn't expose queue details directly
        stats[queue_name] = {
            "length": 0,  # TaskIQ doesn't provide queue length
            "status": "active"
        }
    
    # Add active tasks to default queue for now
    if stats.get("default"):
        stats["default"]["length"] = len(active_tasks)
    
    return {
        "queues": stats,
        "total_tasks": len(active_tasks)
    }


@router.get("/queue/{queue_name}/length", response_model=QueueLengthResponse)
async def get_queue_length(
    queue_name: str = Path(..., description="Queue name"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Get the current length of a specific queue.
    
    Parameters:
        - queue_name: Name of the queue
    """
    # TaskIQ doesn't expose queue length directly
    # Return active tasks count as approximation
    active_tasks = await task_manager.list_active_tasks()
    
    return {
        "queue_name": queue_name,
        "length": len(active_tasks) if queue_name == "default" else 0,
        "status": "active"
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


@router.post("/revoke/batch", response_model=BatchRevokeResponse)
async def revoke_multiple_tasks(
    task_ids: List[str] = Body(..., description="List of task IDs to revoke"),
    terminate: bool = Body(False, description="Terminate tasks if running"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Revoke multiple tasks in batch.
    
    Parameters:
        - task_ids: List of task IDs
        - terminate: Whether to terminate if tasks are currently executing
    """
    results = []
    
    for task_id in task_ids:
        try:
            # Use the single revoke logic
            result = await revoke_task(task_id, terminate, "TERM", current_user)
            results.append(result)
        except Exception as e:
            results.append({
                "task_id": task_id,
                "revoked": False,
                "message": str(e)
            })
    
    successful = [r for r in results if r.get("revoked")]
    failed = [r for r in results if not r.get("revoked")]
    
    return {
        "total_revoked": len(successful),
        "total_failed": len(failed),
        "results": results
    }


# ---------------------------------------------------------------------------
# Task Type Information
# ---------------------------------------------------------------------------

@router.get("/task-types", response_model=Dict[str, str])
async def get_supported_task_types(
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
) -> Dict[str, str]:
    """
    Get all supported task types and their descriptions.
    
    This endpoint is available to all authenticated users.
    """
    return {
        task_type.value: f"Task type for {task_type.value.replace('_', ' ').title()}" 
        for task_type in TaskType
    }


@router.get("/task-types/{task_type}/supported", response_model=TaskTypeSupportResponse)
async def check_task_type_support(
    task_type: str = Path(..., description="Task type to check"),
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
) -> Dict[str, Any]:
    """
    Check if a specific task type is supported.
    
    Parameters:
        - task_type: TaskType enum value to check
    """
    try:
        task_type_enum = TaskType(task_type)
        
        # Check if task function exists
        from app.scheduler import get_task_function
        task_func = get_task_function(task_type_enum)
        is_supported = task_func is not None
        
    except ValueError:
        is_supported = False
        task_type_enum = None
    
    response = {
        "task_type": task_type,
        "supported": is_supported
    }
    
    if is_supported and task_type_enum:
        response["taskiq_task_name"] = TaskRegistry.get_celery_task_name(task_type_enum)
    
    return response


# ---------------------------------------------------------------------------
# Utility Endpoints
# ---------------------------------------------------------------------------

@router.get("/enums", response_model=EnumValuesResponse)
async def get_enum_values(
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
) -> Dict[str, List[str]]:
    """
    Get all available enum values for task configuration.
    
    Useful for frontend dropdowns and validation.
    """
    return {
        "task_types": [t.value for t in TaskType],
        "task_statuses": [s.value for s in ConfigStatus],
        "scheduler_types": [s.value for s in SchedulerType]
    }


@router.post("/validate", response_model=ValidationResponse)
async def validate_task_config(
    config: TaskConfigCreate,
    current_user: Annotated[User, Depends(get_current_active_user)] = None,
) -> Dict[str, Any]:
    """
    Validate a task configuration without creating it.
    
    Useful for form validation before submission.
    """
    try:
        # The validation happens in the Pydantic model
        # Additional custom validation can be added here
        
        # Check if task type is supported
        from app.scheduler import get_task_function
        task_func = get_task_function(config.task_type)
        
        if not task_func:
            return {
                "valid": False,
                "message": f"Task type {config.task_type} is not implemented",
                "config": None
            }
        
        # Validate schedule config based on scheduler type
        if config.scheduler_type == SchedulerType.INTERVAL:
            required = ['hours', 'minutes', 'seconds']
            if not any(config.schedule_config.get(k) for k in required):
                return {
                    "valid": False,
                    "message": "Interval schedule requires at least one time unit",
                    "config": None
                }
        
        elif config.scheduler_type == SchedulerType.CRON:
            # 支持两种cron格式
            has_cron_expression = 'cron_expression' in config.schedule_config
            has_cron_fields = all(field in config.schedule_config for field in ['minute', 'hour', 'day', 'month', 'day_of_week'])
            
            if not has_cron_expression and not has_cron_fields:
                return {
                    "valid": False,
                    "message": "Cron schedule requires either 'cron_expression' or individual cron fields (minute, hour, day, month, day_of_week)",
                    "config": None
                }
        
        elif config.scheduler_type == SchedulerType.DATE:
            if 'run_date' not in config.schedule_config:
                return {
                    "valid": False,
                    "message": "Date schedule requires run_date",
                    "config": None
                }
        
        return {
            "valid": True,
            "message": "Configuration is valid",
            "config": config.dict()
        }
        
    except Exception as e:
        return {
            "valid": False,
            "message": str(e),
            "config": None
        }


# ---------------------------------------------------------------------------
# Statistics and Reports Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats/executions")
async def get_execution_statistics(
    config_id: Optional[int] = Query(None, description="Filter by configuration ID"),
    days: int = Query(7, ge=1, le=365, description="Number of days to include"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Get task execution statistics.
    
    Parameters:
        - config_id: Optional configuration ID to filter
        - days: Number of days to include in statistics
    """
    async with AsyncSessionLocal() as db:
        if config_id:
            stats = await crud_task_execution.get_stats_by_config(db, config_id, days)
        else:
            stats = await crud_task_execution.get_global_stats(db, days)
        
        return stats


@router.get("/stats/events")
async def get_event_statistics(
    config_id: Optional[int] = Query(None, description="Filter by configuration ID"),
    days: int = Query(7, ge=1, le=365, description="Number of days to include"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Get schedule event statistics.
    
    Parameters:
        - config_id: Optional configuration ID to filter
        - days: Number of days to include in statistics
    """
    async with AsyncSessionLocal() as db:
        if config_id:
            stats = await crud_schedule_event.get_stats_by_config(db, config_id, days)
        else:
            stats = await crud_schedule_event.get_global_stats(db, days)
        
        return stats
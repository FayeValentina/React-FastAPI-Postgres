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
    ScheduledJobInfo
)
from app.services.tasks_manager import task_manager
from app.core.task_registry import TaskType, TaskStatus, SchedulerType


router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# System Management Endpoints
# ---------------------------------------------------------------------------

@router.get("/system/status", response_model=SystemStatusResponse)
async def get_system_status(
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> Dict[str, Any]:
    """
    Get comprehensive system status including scheduler, Celery, and configuration statistics.
    
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
    
    # Calculate health status based on system status
    is_healthy = status.get("scheduler_running", False)
    
    return {
        "status": "healthy" if is_healthy else "degraded",
        "scheduler_running": status.get("scheduler_running", False),
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
        - status: Filter by TaskStatus enum value
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
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Get detailed information about a specific task configuration.
    
    Parameters:
        - config_id: Task configuration ID
        - include_stats: Whether to include execution statistics
    """
    config = await task_manager.get_task_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Task configuration not found")
    
    # Optionally add execution statistics
    if include_stats:
        # This would require adding a method to get stats in task_manager
        config["stats"] = {
            "note": "Statistics can be added here"
        }
    
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
        config_id = await task_manager.create_task_config(**config.dict())
        if config_id is None:
            raise HTTPException(status_code=400, detail="Failed to create task configuration")
        
        # Optionally start scheduling immediately
        if auto_start and config.scheduler_type != SchedulerType.MANUAL:
            await task_manager.start_scheduled_task(config_id)
        
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

@router.post("/configs/{config_id}/schedule/start", response_model=OperationResponse)
async def start_scheduled_task(
    config_id: int = Path(..., description="Task configuration ID"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Start scheduling for a task configuration."""
    success = await task_manager.start_scheduled_task(config_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to start scheduled task")
    
    return {"success": True, "message": f"Task {config_id} scheduling started"}


@router.post("/configs/{config_id}/schedule/stop", response_model=OperationResponse)
async def stop_scheduled_task(
    config_id: int = Path(..., description="Task configuration ID"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Stop scheduling for a task configuration."""
    success = task_manager.stop_scheduled_task(config_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to stop scheduled task")
    
    return {"success": True, "message": f"Task {config_id} scheduling stopped"}


@router.post("/configs/{config_id}/schedule/pause", response_model=OperationResponse)
async def pause_scheduled_task(
    config_id: int = Path(..., description="Task configuration ID"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Pause a scheduled task."""
    success = task_manager.pause_scheduled_task(config_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to pause scheduled task")
    
    return {"success": True, "message": f"Task {config_id} paused"}


@router.post("/configs/{config_id}/schedule/resume", response_model=OperationResponse)
async def resume_scheduled_task(
    config_id: int = Path(..., description="Task configuration ID"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Resume a paused task."""
    success = task_manager.resume_scheduled_task(config_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to resume scheduled task")
    
    return {"success": True, "message": f"Task {config_id} resumed"}


@router.post("/configs/{config_id}/schedule/reload", response_model=OperationResponse)
async def reload_scheduled_task(
    config_id: int = Path(..., description="Task configuration ID"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Reload task schedule from database configuration."""
    success = await task_manager.reload_scheduled_task(config_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reload scheduled task")
    
    return {"success": True, "message": f"Task {config_id} reloaded"}


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
    jobs = task_manager.get_scheduled_jobs()
    
    # Filter out paused jobs if requested
    if not include_paused:
        jobs = [job for job in jobs if job.get("next_run_time") is not None]
    
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
        - options: Execution options (countdown, eta, etc.)
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
    if not task_manager.is_task_type_supported(task_type):
        raise HTTPException(status_code=400, detail=f"Unsupported task type: {task_type}")
    
    task_id = await task_manager.execute_task_by_type(
        task_type=task_type,
        task_params=task_params,
        queue=queue,
        **options
    )
    
    if not task_id:
        raise HTTPException(status_code=400, detail="Failed to execute task")
    
    return {
        "task_id": task_id,
        "task_type": task_type,
        "status": "submitted",
        "queue": queue
    }


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
    task_ids = await task_manager.execute_multiple_configs(config_ids, **options)
    
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
    task_ids = await task_manager.execute_batch_by_task_type(task_type, **options)
    
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
    task_id: str = Path(..., description="Celery task ID"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Get the current status of a Celery task.
    
    Parameters:
        - task_id: Celery task ID (UUID format)
    """
    return task_manager.get_task_status(task_id)


@router.get("/active", response_model=List[ActiveTaskInfo])
async def get_active_tasks(
    queue: Optional[str] = Query(None, description="Filter by queue name"),
    worker: Optional[str] = Query(None, description="Filter by worker name"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> List[Dict[str, Any]]:
    """
    Get all currently active Celery tasks.
    
    Parameters:
        - queue: Optional queue name filter
        - worker: Optional worker name filter
    """
    tasks = task_manager.get_active_tasks()
    
    # Apply filters if provided
    if queue:
        tasks = [t for t in tasks if t.get("queue") == queue]
    if worker:
        tasks = [t for t in tasks if t.get("worker") == worker]
    
    return tasks


@router.get("/queues", response_model=QueueStatsResponse)
async def get_queue_stats(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Get statistics for all queues."""
    queues = ["default", "cleanup", "scraping", "high_priority", "low_priority"]
    stats = {}
    
    for queue_name in queues:
        length = task_manager.get_queue_length(queue_name)
        stats[queue_name] = {
            "length": length,
            "status": "active" if length >= 0 else "unknown"
        }
    
    return {
        "queues": stats,
        "total_tasks": sum(q["length"] for q in stats.values() if q["length"] >= 0)
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
    length = task_manager.get_queue_length(queue_name)
    
    return {
        "queue_name": queue_name,
        "length": length,
        "status": "active" if length >= 0 else "error"
    }


@router.post("/revoke/{task_id}", response_model=TaskRevokeResponse)
async def revoke_task(
    task_id: str = Path(..., description="Celery task ID"),
    terminate: bool = Query(False, description="Terminate the task if running"),
    signal: str = Query("TERM", description="Signal to send (TERM or KILL)"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Revoke a Celery task.
    
    Parameters:
        - task_id: Celery task ID
        - terminate: Whether to terminate if the task is currently executing
        - signal: Signal type (TERM for graceful, KILL for force)
    """
    result = task_manager.revoke_task(task_id, terminate)
    return result


@router.post("/revoke/batch", response_model=BatchRevokeResponse)
async def revoke_multiple_tasks(
    task_ids: List[str] = Body(..., description="List of task IDs to revoke"),
    terminate: bool = Body(False, description="Terminate tasks if running"),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """
    Revoke multiple Celery tasks in batch.
    
    Parameters:
        - task_ids: List of Celery task IDs
        - terminate: Whether to terminate if tasks are currently executing
    """
    results = []
    for task_id in task_ids:
        result = task_manager.revoke_task(task_id, terminate)
        results.append(result)
    
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
    Get all supported task types and their Celery task names.
    
    This endpoint is available to all authenticated users.
    """
    return task_manager.get_supported_task_types()


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
    is_supported = task_manager.is_task_type_supported(task_type)
    
    response = {
        "task_type": task_type,
        "supported": is_supported
    }
    
    # Add additional information if supported
    if is_supported:
        all_types = task_manager.get_supported_task_types()
        response["celery_task_name"] = all_types.get(task_type)
    
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
        "task_statuses": [s.value for s in TaskStatus],
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
        # Validate the configuration
        # The validation happens in the Pydantic model
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
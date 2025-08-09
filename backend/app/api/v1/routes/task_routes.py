"""Task management API routes using TaskManager service."""

from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Annotated, Any, Dict, List, Optional

from app.models.user import User
from app.dependencies.current_user import get_current_superuser
from app.schemas.task_config import TaskConfigCreate, TaskConfigUpdate
from app.services.tasks_manager import task_manager


router = APIRouter(prefix="/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# System status
# ---------------------------------------------------------------------------


@router.get("/system-status", response_model=Dict[str, Any])
async def get_system_status(
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> Dict[str, Any]:
    """Return overall task system status."""

    return await task_manager.get_system_status()


# ---------------------------------------------------------------------------
# Task configuration CRUD
# ---------------------------------------------------------------------------


@router.get("/configs", response_model=List[Dict[str, Any]])
async def list_task_configs(
    task_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> List[Dict[str, Any]]:
    """List task configurations."""

    return await task_manager.list_task_configs(task_type=task_type, status=status)


@router.get("/configs/{config_id}", response_model=Dict[str, Any])
async def get_task_config(
    config_id: int,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Get details of a task configuration."""

    config = await task_manager.get_task_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Task configuration not found")
    return config


@router.post("/configs", response_model=Dict[str, Any])
async def create_task_config(
    config: TaskConfigCreate,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Create a new task configuration."""

    config_id = await task_manager.create_task_config(**config.dict())
    if config_id is None:
        raise HTTPException(status_code=400, detail="Failed to create task configuration")
    return {"id": config_id}


@router.put("/configs/{config_id}", response_model=Dict[str, Any])
async def update_task_config(
    config_id: int,
    updates: TaskConfigUpdate,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Update task configuration."""

    success = await task_manager.update_task_config(
        config_id, updates.dict(exclude_unset=True)
    )
    if not success:
        raise HTTPException(status_code=404, detail="Task configuration not found")
    return {"success": True}


@router.delete("/configs/{config_id}", response_model=Dict[str, Any])
async def delete_task_config(
    config_id: int,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Delete task configuration."""

    success = await task_manager.delete_task_config(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task configuration not found")
    return {"success": True}


# ---------------------------------------------------------------------------
# Scheduling operations
# ---------------------------------------------------------------------------


@router.post("/configs/{config_id}/start", response_model=Dict[str, Any])
async def start_scheduled_task(
    config_id: int,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Start scheduling for a task configuration."""

    success = await task_manager.start_scheduled_task(config_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to start scheduled task")
    return {"success": True}


@router.post("/configs/{config_id}/stop", response_model=Dict[str, Any])
def stop_scheduled_task(
    config_id: int,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Stop scheduling for a task configuration."""

    success = task_manager.stop_scheduled_task(config_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to stop scheduled task")
    return {"success": True}


@router.post("/configs/{config_id}/pause", response_model=Dict[str, Any])
def pause_scheduled_task(
    config_id: int,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Pause scheduled task."""

    success = task_manager.pause_scheduled_task(config_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to pause scheduled task")
    return {"success": True}


@router.post("/configs/{config_id}/resume", response_model=Dict[str, Any])
def resume_scheduled_task(
    config_id: int,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Resume scheduled task."""

    success = task_manager.resume_scheduled_task(config_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to resume scheduled task")
    return {"success": True}


@router.get("/scheduled", response_model=List[Dict[str, Any]])
def get_scheduled_jobs(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> List[Dict[str, Any]]:
    """Return all scheduled jobs."""

    return task_manager.get_scheduled_jobs()


# ---------------------------------------------------------------------------
# Task execution
# ---------------------------------------------------------------------------


@router.post("/configs/{config_id}/execute", response_model=Dict[str, Any])
async def execute_task_immediately(
    config_id: int,
    options: Dict[str, Any] = Body(default={}),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Execute a task configuration immediately."""

    task_id = await task_manager.execute_task_immediately(config_id, **options)
    if not task_id:
        raise HTTPException(status_code=400, detail="Failed to execute task")
    return {"task_id": task_id}


@router.post("/execute/task-type", response_model=Dict[str, Any])
async def execute_task_by_type(
    payload: Dict[str, Any] = Body(...),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Execute task directly by task type."""

    task_type = payload.get("task_type")
    if not task_type:
        raise HTTPException(status_code=400, detail="task_type is required")

    task_params = payload.get("task_params")
    queue = payload.get("queue", "default")
    options = {k: v for k, v in payload.items() if k not in {"task_type", "task_params", "queue"}}

    task_id = await task_manager.execute_task_by_type(
        task_type=task_type,
        task_params=task_params,
        queue=queue,
        **options,
    )
    if not task_id:
        raise HTTPException(status_code=400, detail="Failed to execute task")
    return {"task_id": task_id}


@router.post("/execute/configs", response_model=Dict[str, Any])
async def execute_multiple_configs(
    payload: Dict[str, Any] = Body(...),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Execute multiple task configurations."""

    config_ids = payload.get("config_ids")
    if not config_ids:
        raise HTTPException(status_code=400, detail="config_ids is required")
    options = {k: v for k, v in payload.items() if k != "config_ids"}

    task_ids = await task_manager.execute_multiple_configs(config_ids, **options)
    return {"task_ids": task_ids}


@router.post("/execute/batch-type", response_model=Dict[str, Any])
async def execute_batch_by_task_type(
    payload: Dict[str, Any] = Body(...),
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Execute all active task configs of a given type."""

    task_type = payload.get("task_type")
    if not task_type:
        raise HTTPException(status_code=400, detail="task_type is required")
    options = {k: v for k, v in payload.items() if k != "task_type"}

    task_ids = await task_manager.execute_batch_by_task_type(task_type, **options)
    return {"task_ids": task_ids}


# ---------------------------------------------------------------------------
# Task and queue status
# ---------------------------------------------------------------------------


@router.get("/status/{task_id}", response_model=Dict[str, Any])
def get_task_status(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Get status of a Celery task."""

    return task_manager.get_task_status(task_id)


@router.get("/active", response_model=List[Dict[str, Any]])
def get_active_tasks(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> List[Dict[str, Any]]:
    """Get active Celery tasks."""

    return task_manager.get_active_tasks()


@router.get("/queue/{queue_name}/length", response_model=Dict[str, Any])
def get_queue_length(
    queue_name: str,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Get length of a Celery queue."""

    length = task_manager.get_queue_length(queue_name)
    return {"queue_name": queue_name, "length": length}


@router.post("/revoke/{task_id}", response_model=Dict[str, Any])
def revoke_task(
    task_id: str,
    terminate: bool = False,
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, Any]:
    """Revoke a Celery task."""

    return task_manager.revoke_task(task_id, terminate)


@router.get("/task-types", response_model=Dict[str, str])
def get_supported_task_types(
    current_user: Annotated[User, Depends(get_current_superuser)] = None,
) -> Dict[str, str]:
    """Get mapping of supported task types."""

    return task_manager.get_supported_task_types()
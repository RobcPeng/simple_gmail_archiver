import asyncio
from fastapi import APIRouter, HTTPException
from app.main import db
from app.services.task_manager import TaskManager

router = APIRouter(prefix="/api/sync", tags=["sync"])

_task_manager: TaskManager | None = None
_sync_manager = None


def init_sync(task_manager, sync_manager):
    global _task_manager, _sync_manager
    _task_manager = task_manager
    _sync_manager = sync_manager


@router.post("")
async def trigger_sync(full: bool = False, max_messages: int = 0):
    if _sync_manager is None:
        raise HTTPException(status_code=503, detail="Gmail not configured")
    if _task_manager.is_syncing:
        raise HTTPException(status_code=409, detail="Sync already in progress")

    task = _task_manager.create_task("sync")

    async def run():
        try:
            if full:
                await _sync_manager.run_full_sync(max_messages=max_messages)
            else:
                await _sync_manager.run_incremental_sync()
            task.status = "completed"
        except Exception as e:
            task.status = "failed"
            task.error = str(e)

    asyncio.create_task(run())
    return {"task_id": task.task_id, "status": "started"}


@router.get("/status")
async def sync_status():
    state = await db.execute_fetchone("SELECT * FROM sync_state WHERE id = 1")
    has_checkpoint = bool(state["full_sync_in_progress"]) if state else False
    return {
        "is_syncing": _task_manager.is_syncing if _task_manager else False,
        "is_deleting": _task_manager.is_deleting if _task_manager else False,
        "is_busy": _task_manager.is_busy if _task_manager else False,
        "account_email": state["account_email"] if state else None,
        "last_history_id": state["last_history_id"] if state else None,
        "last_full_sync": state["last_full_sync"] if state else None,
        "synced_messages": state["synced_messages"] if state else 0,
        "has_checkpoint": has_checkpoint,
    }

import asyncio
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TaskProgress:
    task_id: str
    task_type: str
    status: str = "pending"  # pending | running | completed | failed
    total: int = 0
    processed: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class TaskManager:
    """Manages mutual exclusion between Gmail API operations.

    Only one Gmail API operation (sync or delete) runs at a time.
    This prevents API quota contention that causes freezes.
    """

    def __init__(self):
        self._gmail_lock = asyncio.Lock()
        self._sync_active = False
        self._delete_active = False
        self._sync_event = asyncio.Event()
        self._sync_event.set()
        self._delete_event = asyncio.Event()
        self._delete_event.set()
        self._tasks: dict[str, TaskProgress] = {}
        self._counter = 0

    # --- Sync lock ---
    async def acquire_sync_lock(self) -> bool:
        if self._gmail_lock.locked():
            return False
        await self._gmail_lock.acquire()
        self._sync_active = True
        self._sync_event.clear()
        return True

    def release_sync_lock(self):
        self._sync_active = False
        self._sync_event.set()
        if self._gmail_lock.locked():
            self._gmail_lock.release()

    async def wait_for_sync_complete(self):
        await self._sync_event.wait()

    # --- Delete lock ---
    async def acquire_delete_lock(self) -> bool:
        if self._gmail_lock.locked():
            return False
        await self._gmail_lock.acquire()
        self._delete_active = True
        self._delete_event.clear()
        return True

    def release_delete_lock(self):
        self._delete_active = False
        self._delete_event.set()
        if self._gmail_lock.locked():
            self._gmail_lock.release()

    async def wait_for_delete_complete(self):
        await self._delete_event.wait()

    # --- Task tracking ---
    def create_task(self, task_type: str) -> TaskProgress:
        self._counter += 1
        task = TaskProgress(
            task_id=f"{task_type}_{self._counter}",
            task_type=task_type,
            started_at=datetime.utcnow(),
            status="running",
        )
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> TaskProgress | None:
        return self._tasks.get(task_id)

    @property
    def is_syncing(self) -> bool:
        return self._sync_active

    @property
    def is_deleting(self) -> bool:
        return self._delete_active

    @property
    def is_busy(self) -> bool:
        return self._gmail_lock.locked()

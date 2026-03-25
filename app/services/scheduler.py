import json
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import Database

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, db: Database):
        self._db = db
        self._scheduler = AsyncIOScheduler()
        self._deletion_manager = None

    def set_deletion_manager(self, dm):
        self._deletion_manager = dm

    async def start(self):
        schedules = await self._db.execute_fetchall(
            "SELECT * FROM deletion_schedules WHERE enabled = 1"
        )
        for s in schedules:
            self._add_job(s)
        self._scheduler.start()

    def stop(self):
        self._scheduler.shutdown(wait=False)

    def _add_job(self, schedule):
        job_id = f"deletion_{schedule['id']}"
        try:
            trigger = CronTrigger.from_crontab(schedule["cron_expression"])
            self._scheduler.add_job(
                self._run_deletion, trigger=trigger, id=job_id,
                args=[schedule["id"]], replace_existing=True,
            )
        except Exception as e:
            logger.error(f"Failed to add schedule {schedule['id']}: {e}")

    async def _run_deletion(self, schedule_id: int):
        schedule = await self._db.execute_fetchone(
            "SELECT * FROM deletion_schedules WHERE id = ? AND enabled = 1",
            (schedule_id,),
        )
        if not schedule or not self._deletion_manager:
            return

        filter_rules = json.loads(schedule["filter_rules"])
        await self._deletion_manager.delete_by_filter(
            filter_rules=filter_rules,
            require_classification=bool(schedule["require_classification"]),
            trigger="scheduled", schedule_id=schedule_id,
        )

        from datetime import datetime
        await self._db.execute(
            "UPDATE deletion_schedules SET last_run = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), schedule_id),
        )

    async def add_schedule(self, schedule_id: int):
        s = await self._db.execute_fetchone(
            "SELECT * FROM deletion_schedules WHERE id = ?", (schedule_id,)
        )
        if s and s["enabled"]:
            self._add_job(s)

    def remove_schedule(self, schedule_id: int):
        job_id = f"deletion_{schedule_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)

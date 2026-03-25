import json
from fastapi import APIRouter, HTTPException, Response
from app.models import DeletionSchedule
from app.main import db

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

_scheduler_service = None


def init_scheduler(scheduler_service):
    global _scheduler_service
    _scheduler_service = scheduler_service


@router.get("")
async def list_schedules():
    rows = await db.execute_fetchall("SELECT * FROM deletion_schedules ORDER BY id")
    result = []
    for r in rows:
        d = dict(r)
        d["filter_rules"] = json.loads(d["filter_rules"]) if isinstance(d["filter_rules"], str) else d["filter_rules"]
        result.append(d)
    return result


@router.post("", status_code=201)
async def create_schedule(schedule: DeletionSchedule):
    await db.execute(
        """INSERT INTO deletion_schedules (name, cron_expression, filter_rules,
           require_classification, enabled)
           VALUES (?, ?, ?, ?, ?)""",
        (schedule.name, schedule.cron_expression, json.dumps(schedule.filter_rules),
         schedule.require_classification, schedule.enabled),
    )
    row = await db.execute_fetchone(
        "SELECT * FROM deletion_schedules ORDER BY id DESC LIMIT 1"
    )
    if _scheduler_service and row["enabled"]:
        await _scheduler_service.add_schedule(row["id"])
    d = dict(row)
    d["filter_rules"] = json.loads(d["filter_rules"])
    return d


@router.put("/{schedule_id}")
async def update_schedule(schedule_id: int, schedule: DeletionSchedule):
    existing = await db.execute_fetchone(
        "SELECT * FROM deletion_schedules WHERE id = ?", (schedule_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.execute(
        """UPDATE deletion_schedules SET name=?, cron_expression=?, filter_rules=?,
           require_classification=?, enabled=? WHERE id=?""",
        (schedule.name, schedule.cron_expression, json.dumps(schedule.filter_rules),
         schedule.require_classification, schedule.enabled, schedule_id),
    )
    if _scheduler_service:
        _scheduler_service.remove_schedule(schedule_id)
        if schedule.enabled:
            await _scheduler_service.add_schedule(schedule_id)
    row = await db.execute_fetchone("SELECT * FROM deletion_schedules WHERE id = ?", (schedule_id,))
    d = dict(row)
    d["filter_rules"] = json.loads(d["filter_rules"])
    return d


@router.delete("/{schedule_id}", status_code=204)
async def delete_schedule(schedule_id: int):
    existing = await db.execute_fetchone(
        "SELECT * FROM deletion_schedules WHERE id = ?", (schedule_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if _scheduler_service:
        _scheduler_service.remove_schedule(schedule_id)
    await db.execute("DELETE FROM deletion_schedules WHERE id = ?", (schedule_id,))
    return Response(status_code=204)

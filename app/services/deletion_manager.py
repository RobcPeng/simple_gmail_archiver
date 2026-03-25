import logging
from datetime import datetime
from app.database import Database
from app.services.gmail import GmailService
from app.services.task_manager import TaskManager

logger = logging.getLogger(__name__)
BATCH_SIZE = 100


class DeletionManager:
    def __init__(self, db: Database, gmail: GmailService, task_manager: TaskManager):
        self._db = db
        self._gmail = gmail
        self._task_manager = task_manager

    async def delete_emails(self, email_ids, trigger, permanent=False, schedule_id=None):
        await self._task_manager.wait_for_sync_complete()
        to_delete = []
        skipped = 0
        for eid in email_ids:
            row = await self._db.execute_fetchone(
                "SELECT id, deleted_from_gmail FROM emails WHERE id = ?", (eid,)
            )
            if row and not row["deleted_from_gmail"]:
                to_delete.append(eid)
            else:
                skipped += 1

        for i in range(0, len(to_delete), BATCH_SIZE):
            batch = to_delete[i : i + BATCH_SIZE]
            if permanent:
                self._gmail.delete_messages(batch)
            else:
                self._gmail.trash_messages(batch)

        now = datetime.utcnow().isoformat()
        deletion_type = "permanently_deleted" if permanent else "trashed"
        for eid in to_delete:
            await self._db.execute(
                """UPDATE emails SET deleted_from_gmail = 1, deletion_type = ?, updated_at = ?
                   WHERE id = ?""",
                (deletion_type, now, eid),
            )
            await self._db.execute(
                """INSERT INTO deletion_log (schedule_id, email_id, deleted_at, trigger)
                   VALUES (?, ?, ?, ?)""",
                (schedule_id, eid, now, trigger),
            )

        return {"deleted": len(to_delete), "skipped": skipped}

    async def delete_by_filter(self, filter_rules, require_classification=True,
                                trigger="scheduled", permanent=False, schedule_id=None):
        conditions = ["deleted_from_gmail = 0"]
        params = []

        if require_classification:
            conditions.append("classification = 'junk'")

        if "sender_email" in filter_rules:
            conditions.append("sender_email = ?")
            params.append(filter_rules["sender_email"])

        if "domain" in filter_rules:
            conditions.append("sender_email LIKE ?")
            params.append(f"%{filter_rules['domain']}")

        if "label" in filter_rules:
            conditions.append("labels LIKE ?")
            params.append(f'%"{filter_rules["label"]}"%')

        if "classification" in filter_rules:
            conditions.append("classification = ?")
            params.append(filter_rules["classification"])

        where = " AND ".join(conditions)
        rows = await self._db.execute_fetchall(
            f"SELECT id FROM emails WHERE {where}", tuple(params)
        )
        email_ids = [r["id"] for r in rows]

        if not email_ids:
            return {"deleted": 0, "skipped": 0}

        return await self.delete_emails(
            email_ids, trigger=trigger, permanent=permanent, schedule_id=schedule_id
        )

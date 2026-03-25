import json
from datetime import datetime
from app.database import Database
from app.services.search import SearchService
from app.services.classifier import Classifier
from app.services.task_manager import TaskManager


class McpTools:
    def __init__(self, db, search, classifier, task_manager, gmail, r2,
                 sync_manager, deletion_manager, scheduler):
        self._db = db
        self._search = search
        self._classifier = classifier
        self._task_manager = task_manager
        self._gmail = gmail
        self._r2 = r2
        self._sync_manager = sync_manager
        self._deletion_manager = deletion_manager
        self._scheduler = scheduler

    # --- Search & Read ---
    async def search_emails(self, query=None, classification=None, sender=None,
                            date_after=None, date_before=None, has_attachments=None,
                            page=1, page_size=50):
        result = await self._search.search(
            query=query, classification=classification, sender=sender,
            date_after=date_after, date_before=date_before,
            has_attachments=has_attachments, page=page, page_size=page_size,
        )
        return {"emails": [e.model_dump() for e in result.emails],
                "total": result.total, "page": result.page, "page_size": result.page_size}

    async def get_email(self, email_id):
        email = await self._search.get_email(email_id)
        if email is None:
            return {"error": "Email not found"}
        return email.model_dump()

    async def download_eml(self, email_id):
        email = await self._search.get_email(email_id)
        if email is None:
            return {"error": "Email not found"}
        if not email.eml_path or email.eml_path == "unrecoverable":
            return {"error": "No .eml file available"}
        url = self._r2.get_download_url(email.eml_path)
        return {"url": url, "email_id": email_id}

    async def get_stats(self):
        total = await self._db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails")
        keep = await self._db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE classification='keep'")
        junk = await self._db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE classification='junk'")
        unclassified = await self._db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE classification='unclassified'")
        deleted = await self._db.execute_fetchone("SELECT COUNT(*) as cnt FROM emails WHERE deleted_from_gmail=1")
        size = await self._db.execute_fetchone("SELECT COALESCE(SUM(size_bytes), 0) as total FROM emails")
        return {
            "total_emails": total["cnt"], "classified_keep": keep["cnt"],
            "classified_junk": junk["cnt"], "unclassified": unclassified["cnt"],
            "deleted_from_gmail": deleted["cnt"], "total_size_bytes": size["total"],
        }

    # --- Sync & Classify ---
    async def trigger_sync(self, full=False):
        if self._task_manager.is_syncing:
            return {"error": "Sync already in progress"}
        import asyncio
        task = self._task_manager.create_task("sync")
        async def run():
            try:
                if full:
                    await self._sync_manager.run_full_sync()
                else:
                    await self._sync_manager.run_incremental_sync()
                task.status = "completed"
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
        asyncio.create_task(run())
        return {"task_id": task.task_id, "status": "started"}

    async def get_sync_status(self):
        state = await self._db.execute_fetchone("SELECT * FROM sync_state WHERE id = 1")
        return {
            "is_syncing": self._task_manager.is_syncing,
            "account_email": state["account_email"] if state else None,
            "last_history_id": state["last_history_id"] if state else None,
            "last_full_sync": state["last_full_sync"] if state else None,
            "synced_messages": state["synced_messages"] if state else 0,
        }

    async def classify_emails(self, email_ids, classification):
        now = datetime.utcnow().isoformat()
        for eid in email_ids:
            await self._db.execute(
                "UPDATE emails SET classification=?, classified_at=?, updated_at=? WHERE id=?",
                (classification, now, now, eid),
            )
        return {"updated": len(email_ids), "classification": classification}

    async def classify_by_sender(self, sender_email, classification):
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            "UPDATE emails SET classification=?, classified_at=?, updated_at=? WHERE sender_email=?",
            (classification, now, now, sender_email),
        )
        row = await self._db.execute_fetchone(
            "SELECT COUNT(*) as cnt FROM emails WHERE sender_email=?", (sender_email,)
        )
        return {"updated": row["cnt"], "sender_email": sender_email, "classification": classification}

    # --- Delete & Schedule ---
    async def delete_emails(self, email_ids, confirm=False):
        if not confirm:
            return {"error": "Must set confirm=true to delete"}
        return await self._deletion_manager.delete_emails(email_ids, trigger="agent")

    async def delete_by_filter(self, filter_rules, confirm=False, permanent=False):
        if not confirm:
            return {"error": "Must set confirm=true to delete"}
        return await self._deletion_manager.delete_by_filter(
            filter_rules=filter_rules, trigger="agent", permanent=permanent,
        )

    async def create_schedule(self, name, cron_expression, filter_rules, require_classification=True):
        await self._db.execute(
            """INSERT INTO deletion_schedules (name, cron_expression, filter_rules, require_classification)
               VALUES (?, ?, ?, ?)""",
            (name, cron_expression, json.dumps(filter_rules), require_classification),
        )
        row = await self._db.execute_fetchone(
            "SELECT * FROM deletion_schedules ORDER BY id DESC LIMIT 1"
        )
        if self._scheduler:
            await self._scheduler.add_schedule(row["id"])
        return dict(row)

    async def update_schedule(self, schedule_id, **kwargs):
        sets, params = [], []
        for key in ("name", "cron_expression", "require_classification", "enabled"):
            if key in kwargs:
                sets.append(f"{key}=?")
                params.append(kwargs[key])
        if "filter_rules" in kwargs:
            sets.append("filter_rules=?")
            params.append(json.dumps(kwargs["filter_rules"]))
        if not sets:
            return {"error": "No fields to update"}
        params.append(schedule_id)
        await self._db.execute(
            f"UPDATE deletion_schedules SET {','.join(sets)} WHERE id=?", tuple(params),
        )
        return {"updated": schedule_id}

    async def list_schedules(self):
        rows = await self._db.execute_fetchall("SELECT * FROM deletion_schedules ORDER BY id")
        result = []
        for r in rows:
            d = dict(r)
            d["filter_rules"] = json.loads(d["filter_rules"]) if isinstance(d["filter_rules"], str) else d["filter_rules"]
            result.append(d)
        return result

    async def delete_schedule(self, schedule_id):
        await self._db.execute("DELETE FROM deletion_schedules WHERE id=?", (schedule_id,))
        if self._scheduler:
            self._scheduler.remove_schedule(schedule_id)
        return {"deleted": schedule_id}

    # --- Rules & Config ---
    async def create_rule(self, name, rule_type, pattern, classification, priority=100):
        await self._db.execute(
            """INSERT INTO classification_rules (name, rule_type, pattern, classification, priority)
               VALUES (?, ?, ?, ?, ?)""",
            (name, rule_type, pattern, classification, priority),
        )
        row = await self._db.execute_fetchone(
            "SELECT * FROM classification_rules ORDER BY id DESC LIMIT 1"
        )
        return dict(row)

    async def update_rule(self, rule_id, **kwargs):
        sets, params = [], []
        for key in ("name", "rule_type", "pattern", "classification", "priority", "enabled"):
            if key in kwargs:
                sets.append(f"{key}=?")
                params.append(kwargs[key])
        if not sets:
            return {"error": "No fields to update"}
        params.append(rule_id)
        await self._db.execute(
            f"UPDATE classification_rules SET {','.join(sets)} WHERE id=?", tuple(params),
        )
        return {"updated": rule_id}

    async def list_rules(self):
        rows = await self._db.execute_fetchall(
            "SELECT * FROM classification_rules ORDER BY priority ASC"
        )
        return [dict(r) for r in rows]

    async def delete_rule(self, rule_id):
        await self._db.execute("DELETE FROM classification_rules WHERE id=?", (rule_id,))
        return {"deleted": rule_id}

    async def get_config(self):
        from app.config import settings
        return {
            "sync_interval_minutes": settings.sync_interval_minutes,
            "r2_bucket_name": settings.r2_bucket_name,
            "r2_configured": bool(settings.r2_access_key_id),
            "gmail_configured": settings.token_path.exists(),
        }

    async def update_config(self, **kwargs):
        return {"error": "Runtime config update not yet implemented"}

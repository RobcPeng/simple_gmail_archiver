import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.main import db
from app.services.search import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/emails", tags=["emails"])


class ClassifyRequest(BaseModel):
    classification: str


class BulkClassifyRequest(BaseModel):
    email_ids: list[str]
    classification: str


@router.get("")
async def search_emails(
    query: str | None = None,
    classification: str | None = None,
    has_attachments: bool | None = None,
    date_after: str | None = None,
    date_before: str | None = None,
    sender: str | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    search = SearchService(db)
    return await search.search(
        query=query, classification=classification,
        has_attachments=has_attachments, date_after=date_after,
        date_before=date_before, sender=sender,
        min_size=min_size, max_size=max_size,
        page=page, page_size=page_size,
    )


@router.get("/{email_id}")
async def get_email(email_id: str):
    search = SearchService(db)
    email = await search.get_email(email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return email


@router.patch("/{email_id}")
async def classify_email(email_id: str, body: ClassifyRequest):
    search = SearchService(db)
    email = await search.get_email(email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="Email not found")
    now = datetime.utcnow().isoformat()
    await db.execute(
        """UPDATE emails SET classification = ?, classified_at = ?, updated_at = ?
           WHERE id = ?""",
        (body.classification, now, now, email_id),
    )

    # Archive or Junk = delete from Gmail (async, don't block response)
    # Skip Gmail deletion if a sync is in progress to avoid API contention
    if body.classification in ("archive", "junk") and not email.deleted_from_gmail:
        from app.services.registry import registry
        if registry.task_manager and registry.task_manager.is_syncing:
            pass  # Classification saved, Gmail deletion deferred until sync finishes
        else:
            asyncio.create_task(_archive_from_gmail([email_id]))

    return {**email.model_dump(), "classification": body.classification, "classified_at": now}


@router.post("/classify-bulk")
async def bulk_classify(body: BulkClassifyRequest):
    now = datetime.utcnow().isoformat()
    placeholders = ",".join("?" for _ in body.email_ids)
    await db.execute(
        f"""UPDATE emails SET classification = ?, classified_at = ?, updated_at = ?
            WHERE id IN ({placeholders})""",
        (body.classification, now, now, *body.email_ids),
    )

    # Archive or Junk = delete from Gmail
    # Skip Gmail deletion if a sync is in progress to avoid API contention
    if body.classification in ("archive", "junk"):
        from app.services.registry import registry
        is_syncing = registry.task_manager and registry.task_manager.is_syncing
        if not is_syncing:
            rows = await db.execute_fetchall(
                f"SELECT id FROM emails WHERE id IN ({placeholders}) AND deleted_from_gmail = 0",
                tuple(body.email_ids),
            )
            ids_to_archive = [r["id"] for r in rows]
            if ids_to_archive:
                asyncio.create_task(_archive_from_gmail(ids_to_archive))

    return {"updated": len(body.email_ids), "classification": body.classification}


@router.get("/review/groups")
async def review_groups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("count", regex="^(count|sender)$"),
):
    """Get unclassified emails grouped by sender, paginated at the group level."""
    order = "cnt DESC" if sort == "count" else "sender_email ASC"
    offset = (page - 1) * page_size

    # Total number of sender groups
    total_row = await db.execute_fetchone(
        "SELECT COUNT(DISTINCT sender_email) as cnt FROM emails WHERE classification = 'unclassified'"
    )
    total_groups = total_row["cnt"]
    total_emails_row = await db.execute_fetchone(
        "SELECT COUNT(*) as cnt FROM emails WHERE classification = 'unclassified'"
    )

    # Get paginated sender groups
    groups = await db.execute_fetchall(
        f"""SELECT sender_email, COUNT(*) as cnt, MIN(date) as oldest, MAX(date) as newest
            FROM emails WHERE classification = 'unclassified'
            GROUP BY sender_email ORDER BY {order} LIMIT ? OFFSET ?""",
        (page_size, offset),
    )

    # For each group, fetch a sample of emails (first 5)
    result = []
    for g in groups:
        sender = g["sender_email"]
        sample = await db.execute_fetchall(
            """SELECT id, subject, snippet, date, sender, sender_email, classification, has_attachments, eml_path, size_bytes
               FROM emails WHERE sender_email = ? AND classification = 'unclassified'
               ORDER BY date DESC LIMIT 5""",
            (sender,),
        )
        # Get all IDs for bulk classify (just IDs, not full emails)
        all_ids = await db.execute_fetchall(
            "SELECT id FROM emails WHERE sender_email = ? AND classification = 'unclassified'",
            (sender,),
        )
        result.append({
            "sender_email": sender,
            "count": g["cnt"],
            "oldest": g["oldest"],
            "newest": g["newest"],
            "email_ids": [r["id"] for r in all_ids],
            "sample_emails": [dict(r) for r in sample],
        })

    return {
        "groups": result,
        "total_groups": total_groups,
        "total_emails": total_emails_row["cnt"],
        "page": page,
        "page_size": page_size,
    }


async def _archive_from_gmail(email_ids: list[str]):
    """Trash emails from Gmail in batches. Acquires delete lock to prevent API contention."""
    from app.services.registry import registry
    if not registry.gmail:
        logger.warning("Cannot archive from Gmail — not authenticated")
        return
    if not registry.task_manager:
        return

    # Wait for any sync to finish, then acquire delete lock
    acquired = await registry.task_manager.acquire_delete_lock()
    if not acquired:
        logger.warning(f"Gmail API busy — deferring deletion of {len(email_ids)} emails")
        return

    try:
        loop = asyncio.get_event_loop()
        total = len(email_ids)
        deleted = 0

        for i in range(0, total, 10):
            batch = email_ids[i:i + 10]
            await loop.run_in_executor(None, registry.gmail.trash_messages, batch)

            now = datetime.utcnow().isoformat()
            for eid in batch:
                await db.execute(
                    """UPDATE emails SET deleted_from_gmail = 1, deletion_type = 'trashed', updated_at = ?
                       WHERE id = ?""",
                    (now, eid),
                )
                await db.execute(
                    """INSERT INTO deletion_log (email_id, deleted_at, trigger)
                       VALUES (?, ?, 'manual')""",
                    (eid, now),
                )
            deleted += len(batch)
            logger.info(f"Archived {deleted}/{total} emails from Gmail")
            await asyncio.sleep(0.5)

        logger.info(f"Archive complete: {total} emails trashed from Gmail")
    except Exception as e:
        logger.error(f"Failed to archive from Gmail: {e}")
    finally:
        registry.task_manager.release_delete_lock()

from fastapi import APIRouter
from app.main import db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats():
    rows = await db.execute_fetchall(
        """SELECT classification,
                  COUNT(*) as cnt,
                  COALESCE(SUM(size_bytes), 0) as size
           FROM emails GROUP BY classification"""
    )
    by_class = {r["classification"]: {"count": r["cnt"], "size": r["size"]} for r in rows}

    total = await db.execute_fetchone(
        "SELECT COUNT(*) as cnt, COALESCE(SUM(size_bytes), 0) as size FROM emails"
    )
    deleted = await db.execute_fetchone(
        "SELECT COUNT(*) as cnt, COALESCE(SUM(size_bytes), 0) as size FROM emails WHERE deleted_from_gmail=1"
    )

    def get(cls: str):
        return by_class.get(cls, {"count": 0, "size": 0})

    return {
        "total_emails": total["cnt"],
        "total_size_bytes": total["size"],
        "classified_archive": get("archive")["count"],
        "classified_archive_size": get("archive")["size"],
        "classified_keep": get("keep")["count"],
        "classified_keep_size": get("keep")["size"],
        "classified_junk": get("junk")["count"],
        "classified_junk_size": get("junk")["size"],
        "unclassified": get("unclassified")["count"],
        "unclassified_size": get("unclassified")["size"],
        "deleted_from_gmail": deleted["cnt"],
        "deleted_from_gmail_size": deleted["size"],
    }

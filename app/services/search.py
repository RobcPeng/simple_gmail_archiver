import json
from app.database import Database
from app.models import Email, EmailSearchResult


class SearchService:
    def __init__(self, db: Database):
        self.db = db

    async def search(
        self,
        query: str | None = None,
        classification: str | None = None,
        has_attachments: bool | None = None,
        date_after: str | None = None,
        date_before: str | None = None,
        sender: str | None = None,
        min_size: int | None = None,
        max_size: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> EmailSearchResult:
        conditions = []
        params = []

        if query:
            conditions.append(
                "e.rowid IN (SELECT rowid FROM emails_fts WHERE emails_fts MATCH ?)"
            )
            params.append(query)

        if classification:
            conditions.append("e.classification = ?")
            params.append(classification)

        if has_attachments is not None:
            conditions.append("e.has_attachments = ?")
            params.append(1 if has_attachments else 0)

        if date_after:
            conditions.append("e.date >= ?")
            params.append(date_after)

        if date_before:
            conditions.append("e.date <= ?")
            params.append(date_before)

        if sender:
            conditions.append("(e.sender_email LIKE ? OR e.sender LIKE ?)")
            params.extend([f"%{sender}%", f"%{sender}%"])

        if min_size is not None:
            conditions.append("e.size_bytes >= ?")
            params.append(min_size)

        if max_size is not None:
            conditions.append("e.size_bytes <= ?")
            params.append(max_size)

        where = " AND ".join(conditions) if conditions else "1=1"

        count_row = await self.db.execute_fetchone(
            f"SELECT COUNT(*) as cnt FROM emails e WHERE {where}", tuple(params)
        )
        total = count_row["cnt"]

        offset = (page - 1) * page_size
        rows = await self.db.execute_fetchall(
            f"""SELECT * FROM emails e WHERE {where}
                ORDER BY e.date DESC LIMIT ? OFFSET ?""",
            tuple(params + [page_size, offset]),
        )

        emails = [self._row_to_email(r) for r in rows]
        return EmailSearchResult(emails=emails, total=total, page=page, page_size=page_size)

    async def get_email(self, email_id: str) -> Email | None:
        row = await self.db.execute_fetchone("SELECT * FROM emails WHERE id = ?", (email_id,))
        if row is None:
            return None
        return self._row_to_email(row)

    def _row_to_email(self, row) -> Email:
        d = dict(row)
        # Parse JSON fields
        for field in ("recipients", "labels"):
            if d.get(field) and isinstance(d[field], str):
                d[field] = json.loads(d[field])
        return Email(**d)

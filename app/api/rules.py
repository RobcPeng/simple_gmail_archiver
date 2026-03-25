from fastapi import APIRouter, HTTPException, Response
from app.models import ClassificationRule
from app.main import db

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("")
async def list_rules():
    rows = await db.execute_fetchall(
        "SELECT * FROM classification_rules ORDER BY priority ASC"
    )
    return [dict(r) for r in rows]


@router.post("", status_code=201)
async def create_rule(rule: ClassificationRule):
    await db.execute(
        """INSERT INTO classification_rules (name, rule_type, pattern, classification, priority, enabled)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (rule.name, rule.rule_type, rule.pattern, rule.classification, rule.priority, rule.enabled),
    )
    row = await db.execute_fetchone(
        "SELECT * FROM classification_rules ORDER BY id DESC LIMIT 1"
    )
    return dict(row)


@router.put("/{rule_id}")
async def update_rule(rule_id: int, rule: ClassificationRule):
    existing = await db.execute_fetchone(
        "SELECT * FROM classification_rules WHERE id = ?", (rule_id,)
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.execute(
        """UPDATE classification_rules
           SET name=?, rule_type=?, pattern=?, classification=?, priority=?, enabled=?
           WHERE id=?""",
        (rule.name, rule.rule_type, rule.pattern, rule.classification,
         rule.priority, rule.enabled, rule_id),
    )
    row = await db.execute_fetchone("SELECT * FROM classification_rules WHERE id = ?", (rule_id,))
    return dict(row)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: int):
    existing = await db.execute_fetchone(
        "SELECT * FROM classification_rules WHERE id = ?", (rule_id,)
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.execute("DELETE FROM classification_rules WHERE id = ?", (rule_id,))
    return Response(status_code=204)

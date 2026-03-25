import fnmatch
import json
import re
from dataclasses import dataclass
from app.database import Database


@dataclass
class ClassificationResult:
    classification: str  # 'keep' | 'junk' | 'unclassified'
    rule_name: str | None = None
    reason: str | None = None


class Classifier:
    def __init__(self, db: Database):
        self.db = db

    async def classify_email(self, email_id: str) -> ClassificationResult:
        email = await self.db.execute_fetchone("SELECT * FROM emails WHERE id = ?", (email_id,))
        if email is None:
            return ClassificationResult(classification="unclassified", reason="Email not found")

        rules = await self.db.execute_fetchall(
            "SELECT * FROM classification_rules WHERE enabled = 1 ORDER BY priority ASC"
        )

        for rule in rules:
            if self._rule_matches(rule, email):
                return ClassificationResult(
                    classification=rule["classification"],
                    rule_name=rule["name"],
                    reason=f"Matched rule: {rule['name']} ({rule['rule_type']}: {rule['pattern']})",
                )

        return ClassificationResult(classification="unclassified", reason="No matching rule")

    def _rule_matches(self, rule, email) -> bool:
        rule_type = rule["rule_type"]
        pattern = rule["pattern"]

        if rule_type == "sender":
            return (email["sender_email"] or "").lower() == pattern.lower()

        elif rule_type == "domain":
            sender = email["sender_email"] or ""
            return fnmatch.fnmatch(sender.lower(), pattern.lower())

        elif rule_type == "label":
            labels_raw = email["labels"] or "[]"
            labels = json.loads(labels_raw) if isinstance(labels_raw, str) else labels_raw
            return pattern in labels

        elif rule_type == "keyword":
            text = f"{email['subject'] or ''} {email['body_text'] or ''}".lower()
            return pattern.lower() in text

        elif rule_type == "size":
            match = re.match(r"([<>])(\d+)", pattern)
            if not match:
                return False
            op, threshold = match.group(1), int(match.group(2))
            size = email["size_bytes"] or 0
            return (size > threshold) if op == ">" else (size < threshold)

        return False

import pytest
from app.services.classifier import Classifier


@pytest.fixture
async def classifier(db):
    return Classifier(db)


async def _add_rule(db, name, rule_type, pattern, classification, priority=100):
    await db.execute(
        """INSERT INTO classification_rules (name, rule_type, pattern, classification, priority)
           VALUES (?, ?, ?, ?, ?)""",
        (name, rule_type, pattern, classification, priority),
    )


async def _add_email(db, id, sender_email="test@test.com", subject="Test", body="Body",
                      labels=None, size_bytes=100):
    import json
    await db.execute(
        """INSERT INTO emails (id, sender_email, subject, body_text, labels, size_bytes,
           classification, synced_at) VALUES (?, ?, ?, ?, ?, ?, 'unclassified', datetime('now'))""",
        (id, sender_email, subject, body, json.dumps(labels or []), size_bytes),
    )


async def test_sender_rule_matches(classifier, db):
    await _add_rule(db, "Block spam", "sender", "spam@junk.com", "junk")
    await _add_email(db, "msg_1", sender_email="spam@junk.com")
    result = await classifier.classify_email("msg_1")
    assert result.classification == "junk"


async def test_domain_rule_wildcard(classifier, db):
    await _add_rule(db, "Block marketing", "domain", "*.marketing.*", "junk")
    await _add_email(db, "msg_1", sender_email="offers@email.marketing.co")
    result = await classifier.classify_email("msg_1")
    assert result.classification == "junk"


async def test_label_rule(classifier, db):
    await _add_rule(db, "Promos are junk", "label", "CATEGORY_PROMOTIONS", "junk")
    await _add_email(db, "msg_1", labels=["CATEGORY_PROMOTIONS", "UNREAD"])
    result = await classifier.classify_email("msg_1")
    assert result.classification == "junk"


async def test_keyword_rule(classifier, db):
    await _add_rule(db, "Unsubscribe = junk", "keyword", "unsubscribe", "junk")
    await _add_email(db, "msg_1", body="Click here to unsubscribe from this list")
    result = await classifier.classify_email("msg_1")
    assert result.classification == "junk"


async def test_size_rule(classifier, db):
    await _add_rule(db, "Big emails = keep", "size", ">5000000", "keep", priority=1)
    await _add_email(db, "msg_1", size_bytes=10_000_000)
    result = await classifier.classify_email("msg_1")
    assert result.classification == "keep"


async def test_priority_ordering(classifier, db):
    await _add_rule(db, "Keep important", "label", "IMPORTANT", "keep", priority=1)
    await _add_rule(db, "Promos junk", "label", "CATEGORY_PROMOTIONS", "junk", priority=10)
    await _add_email(db, "msg_1", labels=["IMPORTANT", "CATEGORY_PROMOTIONS"])
    result = await classifier.classify_email("msg_1")
    assert result.classification == "keep"


async def test_no_matching_rule_returns_unclassified(classifier, db):
    await _add_rule(db, "Block spam", "sender", "spam@junk.com", "junk")
    await _add_email(db, "msg_1", sender_email="friend@gmail.com")
    result = await classifier.classify_email("msg_1")
    assert result.classification == "unclassified"


async def test_disabled_rule_skipped(classifier, db):
    await db.execute(
        """INSERT INTO classification_rules (name, rule_type, pattern, classification, priority, enabled)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("Disabled", "sender", "test@test.com", "junk", 1, False),
    )
    await _add_email(db, "msg_1", sender_email="test@test.com")
    result = await classifier.classify_email("msg_1")
    assert result.classification == "unclassified"

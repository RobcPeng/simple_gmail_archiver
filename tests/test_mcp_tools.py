import pytest
from unittest.mock import MagicMock
from app.mcp.tools import McpTools


@pytest.fixture
async def mcp_tools(db):
    from app.services.search import SearchService
    from app.services.classifier import Classifier
    from app.services.task_manager import TaskManager
    search = SearchService(db)
    classifier = Classifier(db)
    task_mgr = TaskManager()
    tools = McpTools(
        db=db, search=search, classifier=classifier,
        task_manager=task_mgr, gmail=MagicMock(),
        r2=MagicMock(), sync_manager=MagicMock(),
        deletion_manager=MagicMock(), scheduler=MagicMock(),
    )
    return tools


async def _seed(db):
    for i in range(3):
        await db.execute(
            """INSERT INTO emails (id, subject, sender_email, body_text, snippet,
               classification, synced_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (f"msg_{i}", f"Subject {i}", f"s{i}@test.com", f"Body {i}", f"Snippet {i}",
             "keep" if i < 2 else "junk"),
        )
        await db.execute(
            """INSERT INTO emails_fts (rowid, subject, sender, body_text, snippet)
               VALUES ((SELECT rowid FROM emails WHERE id = ?), ?, ?, ?, ?)""",
            (f"msg_{i}", f"Subject {i}", f"Sender {i}", f"Body {i}", f"Snippet {i}"),
        )


async def test_search_emails_tool(mcp_tools, db):
    await _seed(db)
    result = await mcp_tools.search_emails(query="Subject")
    assert result["total"] == 3


async def test_get_email_tool(mcp_tools, db):
    await _seed(db)
    result = await mcp_tools.get_email(email_id="msg_0")
    assert result["id"] == "msg_0"


async def test_get_stats_tool(mcp_tools, db):
    await _seed(db)
    result = await mcp_tools.get_stats()
    assert result["total_emails"] == 3
    assert result["classified_keep"] == 2
    assert result["classified_junk"] == 1


async def test_classify_emails_tool(mcp_tools, db):
    await _seed(db)
    result = await mcp_tools.classify_emails(email_ids=["msg_2"], classification="keep")
    assert result["updated"] == 1
    row = await db.execute_fetchone("SELECT classification FROM emails WHERE id = 'msg_2'")
    assert row["classification"] == "keep"


async def test_list_rules_tool(mcp_tools, db):
    await db.execute(
        """INSERT INTO classification_rules (name, rule_type, pattern, classification, priority)
           VALUES (?, ?, ?, ?, ?)""",
        ("Test Rule", "sender", "spam@junk.com", "junk", 10),
    )
    result = await mcp_tools.list_rules()
    assert len(result) == 1
    assert result[0]["name"] == "Test Rule"

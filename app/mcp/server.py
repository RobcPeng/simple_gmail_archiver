from mcp.server.fastmcp import FastMCP

mcp = FastMCP("GmailVault", instructions="Gmail management and archival system")

_tools = None


def init_mcp_tools(tools):
    global _tools
    _tools = tools


@mcp.tool()
async def search_emails(query: str = "", classification: str = "", sender: str = "",
                        date_after: str = "", date_before: str = "",
                        page: int = 1, page_size: int = 50) -> dict:
    """Search archived emails with filters. Returns paginated results."""
    return await _tools.search_emails(
        query=query or None, classification=classification or None,
        sender=sender or None, date_after=date_after or None,
        date_before=date_before or None, page=page, page_size=page_size,
    )


@mcp.tool()
async def get_email(email_id: str) -> dict:
    """Get full email details by Gmail message ID."""
    return await _tools.get_email(email_id)


@mcp.tool()
async def download_eml(email_id: str) -> dict:
    """Get a pre-signed R2 URL to download the .eml file."""
    return await _tools.download_eml(email_id)


@mcp.tool()
async def get_stats() -> dict:
    """Get archive statistics: counts by classification, storage usage."""
    return await _tools.get_stats()


@mcp.tool()
async def trigger_sync(full: bool = False) -> dict:
    """Start a Gmail sync. Set full=True for full sync, False for incremental."""
    return await _tools.trigger_sync(full=full)


@mcp.tool()
async def get_sync_status() -> dict:
    """Check current sync status and progress."""
    return await _tools.get_sync_status()


@mcp.tool()
async def classify_emails(email_ids: list[str], classification: str) -> dict:
    """Classify emails as 'keep' or 'junk'. Accepts list of email IDs."""
    return await _tools.classify_emails(email_ids, classification)


@mcp.tool()
async def classify_by_sender(sender_email: str, classification: str) -> dict:
    """Classify all emails from a sender address as 'keep' or 'junk'."""
    return await _tools.classify_by_sender(sender_email, classification)


@mcp.tool()
async def delete_emails(email_ids: list[str], confirm: bool = False) -> dict:
    """Delete specific emails from Gmail by ID. Set confirm=True to execute."""
    return await _tools.delete_emails(email_ids, confirm=confirm)


@mcp.tool()
async def delete_by_filter(filter_rules: dict, confirm: bool = False,
                           permanent: bool = False) -> dict:
    """Bulk delete emails matching a filter. Requires confirm=True."""
    return await _tools.delete_by_filter(filter_rules, confirm=confirm, permanent=permanent)


@mcp.tool()
async def create_schedule(name: str, cron_expression: str, filter_rules: dict,
                          require_classification: bool = True) -> dict:
    """Create a new deletion schedule with cron expression."""
    return await _tools.create_schedule(name, cron_expression, filter_rules, require_classification)


@mcp.tool()
async def update_schedule(schedule_id: int, name: str = "", cron_expression: str = "",
                          enabled: bool = True) -> dict:
    """Update an existing deletion schedule."""
    kwargs = {}
    if name: kwargs["name"] = name
    if cron_expression: kwargs["cron_expression"] = cron_expression
    kwargs["enabled"] = enabled
    return await _tools.update_schedule(schedule_id, **kwargs)


@mcp.tool()
async def list_schedules() -> list:
    """List all deletion schedules."""
    return await _tools.list_schedules()


@mcp.tool()
async def delete_schedule(schedule_id: int) -> dict:
    """Remove a deletion schedule."""
    return await _tools.delete_schedule(schedule_id)


@mcp.tool()
async def create_rule(name: str, rule_type: str, pattern: str,
                      classification: str, priority: int = 100) -> dict:
    """Create a classification rule. Types: sender, domain, label, keyword, size."""
    return await _tools.create_rule(name, rule_type, pattern, classification, priority)


@mcp.tool()
async def update_rule(rule_id: int, name: str = "", pattern: str = "",
                      classification: str = "", priority: int = -1) -> dict:
    """Update a classification rule."""
    kwargs = {}
    if name: kwargs["name"] = name
    if pattern: kwargs["pattern"] = pattern
    if classification: kwargs["classification"] = classification
    if priority >= 0: kwargs["priority"] = priority
    return await _tools.update_rule(rule_id, **kwargs)


@mcp.tool()
async def list_rules() -> list:
    """List all classification rules ordered by priority."""
    return await _tools.list_rules()


@mcp.tool()
async def delete_rule(rule_id: int) -> dict:
    """Remove a classification rule."""
    return await _tools.delete_rule(rule_id)


@mcp.tool()
async def get_config() -> dict:
    """Read current app configuration."""
    return await _tools.get_config()


@mcp.tool()
async def update_config(sync_interval_minutes: int = -1) -> dict:
    """Update app settings. Pass -1 to leave unchanged."""
    kwargs = {}
    if sync_interval_minutes >= 0:
        kwargs["sync_interval_minutes"] = sync_interval_minutes
    return await _tools.update_config(**kwargs)


# --- MCP Resources ---
@mcp.resource("email://stats")
async def resource_stats() -> str:
    """Current archive statistics."""
    import json
    return json.dumps(await _tools.get_stats())


@mcp.resource("email://sync-status")
async def resource_sync_status() -> str:
    """Live sync progress."""
    import json
    return json.dumps(await _tools.get_sync_status())


@mcp.resource("email://schedules")
async def resource_schedules() -> str:
    """All deletion schedules."""
    import json
    return json.dumps(await _tools.list_schedules())


@mcp.resource("email://rules")
async def resource_rules() -> str:
    """All classification rules."""
    import json
    return json.dumps(await _tools.list_rules())


@mcp.resource("email://recent-deletions")
async def resource_recent_deletions() -> str:
    """Last 50 deletion log entries."""
    import json
    rows = await _tools._db.execute_fetchall(
        "SELECT * FROM deletion_log ORDER BY deleted_at DESC LIMIT 50"
    )
    return json.dumps([dict(r) for r in rows])

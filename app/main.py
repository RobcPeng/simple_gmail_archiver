from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from app.database import Database

db = Database(settings.db_path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.initialize()

    from app.services.task_manager import TaskManager
    from app.services.classifier import Classifier
    from app.services.search import SearchService
    from app.services.scheduler import SchedulerService
    from app.mcp.tools import McpTools
    from app.mcp.server import init_mcp_tools
    from app.services.registry import registry

    task_manager = TaskManager()
    classifier = Classifier(db)

    # Populate registry
    registry.db = db
    registry.task_manager = task_manager
    registry.classifier = classifier

    # Try to init Gmail services (may fail if not yet authenticated)
    registry.init_gmail_services()

    # Scheduler
    scheduler = SchedulerService(db)
    registry.scheduler = scheduler
    if registry.deletion_manager:
        scheduler.set_deletion_manager(registry.deletion_manager)
    await scheduler.start()

    # Wire into API modules
    from app.api.sync import init_sync
    from app.api.schedules import init_scheduler
    init_sync(task_manager, registry.sync_manager)
    init_scheduler(scheduler)

    # MCP — uses registry so it picks up services after re-init too
    mcp_tools = McpTools(
        db=db, search=SearchService(db), classifier=classifier,
        task_manager=task_manager, gmail=registry.gmail, r2=registry.r2,
        sync_manager=registry.sync_manager, deletion_manager=registry.deletion_manager,
        scheduler=scheduler,
    )
    init_mcp_tools(mcp_tools)

    yield

    scheduler.stop()
    await db.close()


def create_app() -> FastAPI:
    app = FastAPI(title="GmailVault", version="0.1.0", lifespan=lifespan)

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    from app.api.emails import router as emails_router
    app.include_router(emails_router)

    from app.api.rules import router as rules_router
    app.include_router(rules_router)

    from app.api.auth import router as auth_router
    app.include_router(auth_router)

    from app.api.sync import router as sync_router
    app.include_router(sync_router)

    from app.api.schedules import router as schedules_router
    app.include_router(schedules_router)

    from app.api.stats import router as stats_router
    app.include_router(stats_router)

    # MCP SSE endpoint (must be before SPA catch-all)
    from app.mcp.server import mcp as mcp_server
    app.mount("/mcp", mcp_server.sse_app())

    # Serve React SPA static files
    frontend_dist = Path(__file__).parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()

"""
Service registry — allows lazy initialization and re-initialization
of Gmail-dependent services after OAuth completes.
"""
from app.config import settings


class ServiceRegistry:
    def __init__(self):
        self.db = None
        self.task_manager = None
        self.classifier = None
        self.gmail = None
        self.r2 = None
        self.sync_manager = None
        self.deletion_manager = None
        self.scheduler = None

    def init_gmail_services(self):
        """(Re)initialize Gmail-dependent services. Call after OAuth completes."""
        from app.services.gmail import GmailService
        from app.services.r2 import R2Service
        from app.services.sync_manager import SyncManager
        from app.services.deletion_manager import DeletionManager

        gmail = GmailService(settings.client_secret_path, settings.token_path)
        if not gmail.authenticate():
            return False

        self.gmail = gmail

        # R2
        if settings.r2_access_key_id and not self.r2:
            self.r2 = R2Service(settings)

        # Managers
        self.sync_manager = SyncManager(
            self.db, self.gmail, self.r2, self.classifier, self.task_manager
        )
        self.deletion_manager = DeletionManager(
            self.db, self.gmail, self.task_manager
        )

        # Re-wire scheduler
        if self.scheduler:
            self.scheduler.set_deletion_manager(self.deletion_manager)

        # Re-wire sync API
        from app.api.sync import init_sync
        init_sync(self.task_manager, self.sync_manager)

        return True


registry = ServiceRegistry()

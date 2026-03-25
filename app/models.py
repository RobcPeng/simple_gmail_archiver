from datetime import datetime
from pydantic import BaseModel


class Email(BaseModel):
    id: str
    thread_id: str | None = None
    subject: str | None = None
    sender: str | None = None
    sender_email: str | None = None
    recipients: dict | None = None
    date: str | None = None
    snippet: str | None = None
    body_text: str | None = None
    body_html: str | None = None
    labels: list[str] | None = None
    size_bytes: int | None = None
    has_attachments: bool = False
    classification: str = "unclassified"
    classification_reason: str | None = None
    eml_path: str | None = None
    synced_at: datetime | None = None
    classified_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_from_gmail: bool = False
    deletion_type: str | None = None


class EmailSearchResult(BaseModel):
    emails: list[Email]
    total: int
    page: int
    page_size: int


class Attachment(BaseModel):
    id: int | None = None
    email_id: str
    filename: str
    mime_type: str | None = None
    size_bytes: int | None = None


class SyncState(BaseModel):
    account_email: str | None = None
    last_history_id: str | None = None
    last_full_sync: datetime | None = None
    total_messages: int = 0
    synced_messages: int = 0


class DeletionSchedule(BaseModel):
    id: int | None = None
    name: str
    cron_expression: str
    filter_rules: dict
    require_classification: bool = True
    enabled: bool = True
    last_run: datetime | None = None
    created_at: datetime | None = None


class DeletionLog(BaseModel):
    id: int | None = None
    schedule_id: int | None = None
    email_id: str
    deleted_at: datetime | None = None
    trigger: str  # 'scheduled' | 'manual' | 'agent'


class ClassificationRule(BaseModel):
    id: int | None = None
    name: str
    rule_type: str  # 'sender' | 'domain' | 'label' | 'keyword' | 'size'
    pattern: str
    classification: str  # 'junk' | 'keep'
    priority: int = 100
    enabled: bool = True
    created_at: datetime | None = None


class Stats(BaseModel):
    total_emails: int = 0
    classified_keep: int = 0
    classified_junk: int = 0
    unclassified: int = 0
    deleted_from_gmail: int = 0
    total_size_bytes: int = 0

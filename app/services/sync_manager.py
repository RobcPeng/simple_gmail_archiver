import asyncio
import base64
import email
import email.policy
import json
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from app.database import Database
from app.services.gmail import GmailService
from app.services.r2 import R2Service
from app.services.classifier import Classifier
from app.services.task_manager import TaskManager

logger = logging.getLogger(__name__)


class SyncManager:
    def __init__(self, db, gmail, r2, classifier, task_manager):
        self._db = db
        self._gmail = gmail
        self._r2 = r2
        self._classifier = classifier
        self._task_manager = task_manager

    async def run_full_sync(self, max_messages: int = 0):
        """Full paginated sync. max_messages: 0=unlimited, >0=cap."""
        acquired = await self._task_manager.acquire_sync_lock()
        if not acquired:
            raise RuntimeError("Sync already in progress")
        try:
            await self._do_full_sync(max_messages=max_messages)
        finally:
            self._task_manager.release_sync_lock()

    async def run_incremental_sync(self):
        """Sync only new messages since last history ID. Acquires sync lock."""
        acquired = await self._task_manager.acquire_sync_lock()
        if not acquired:
            raise RuntimeError("Sync already in progress")
        try:
            state = await self._db.execute_fetchone("SELECT * FROM sync_state WHERE id = 1")
            history_id = state["last_history_id"]

            if not history_id:
                await self._do_full_sync()
                return

            history, new_id = self._gmail.list_history(history_id)
            if history is None:
                logger.warning("History ID expired, falling back to full sync")
                await self._do_full_sync()
                return

            for record in history:
                for added in record.get("messagesAdded", []):
                    msg_id = added["message"]["id"]
                    existing = await self._db.execute_fetchone(
                        "SELECT id FROM emails WHERE id = ?", (msg_id,)
                    )
                    if not existing:
                        await self._process_message(msg_id)

            if new_id:
                await self._db.execute(
                    "UPDATE sync_state SET last_history_id = ? WHERE id = 1",
                    (new_id,),
                )
        finally:
            self._task_manager.release_sync_lock()

    async def _do_full_sync(self, max_messages: int = 0):
        """Internal full sync with checkpointing.
        Resumes from last page_token if a previous sync was interrupted.
        max_messages: 0 = unlimited, >0 = stop after N new messages synced."""
        profile = self._gmail.get_profile()
        await self._db.execute(
            "UPDATE sync_state SET account_email = ? WHERE id = 1",
            (profile.get("emailAddress"),),
        )

        # Check for a checkpoint from a previous interrupted sync
        state = await self._db.execute_fetchone("SELECT * FROM sync_state WHERE id = 1")
        page_token = None
        if state["full_sync_in_progress"] and state["full_sync_page_token"]:
            page_token = state["full_sync_page_token"]
            logger.info(f"Resuming full sync from checkpoint (page_token exists)")

        # Mark sync as in progress with max_messages
        await self._db.execute(
            """UPDATE sync_state SET full_sync_in_progress = 1, full_sync_max_messages = ?
               WHERE id = 1""",
            (max_messages,),
        )

        total_synced = 0
        batch_size = min(max_messages, 500) if max_messages else 500
        try:
            while True:
                messages, next_page_token = self._gmail.list_messages(
                    max_results=batch_size, page_token=page_token
                )
                if not messages:
                    break

                for msg_ref in messages:
                    if max_messages and total_synced >= max_messages:
                        break

                    msg_id = msg_ref["id"]
                    existing = await self._db.execute_fetchone(
                        "SELECT id FROM emails WHERE id = ?", (msg_id,)
                    )
                    if existing:
                        continue

                    await self._process_message_with_retry(msg_id)
                    total_synced += 1

                    # Throttle: ~10 messages/sec to stay within Gmail API quotas
                    await asyncio.sleep(0.1)

                # Checkpoint after every batch — save the next page token
                await self._db.execute(
                    """UPDATE sync_state SET full_sync_page_token = ?,
                       synced_messages = synced_messages + ?
                       WHERE id = 1""",
                    (next_page_token, total_synced),
                )
                # Reset counter for next batch's delta
                total_synced_this_batch = total_synced
                total_synced = 0
                logger.info(f"Checkpoint saved — {total_synced_this_batch} new emails this batch")

                page_token = next_page_token
                if not page_token or (max_messages and total_synced_this_batch >= max_messages):
                    break

        except Exception as e:
            # Crash/error — checkpoint is saved, will resume on next full sync
            logger.error(f"Sync interrupted: {e}. Will resume from checkpoint on next sync.")
            raise

        # Success — clear checkpoint
        now = datetime.utcnow().isoformat()
        await self._db.execute(
            """UPDATE sync_state SET full_sync_in_progress = 0,
               full_sync_page_token = NULL, last_full_sync = ?
               WHERE id = 1""",
            (now,),
        )
        logger.info("Full sync complete")

    async def _process_message_with_retry(self, msg_id: str, max_retries: int = 3):
        """Process a message with exponential backoff on rate limit errors."""
        for attempt in range(max_retries):
            try:
                await self._process_message(msg_id)
                return
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "rate" in err_str or "quota" in err_str:
                    wait = 2 ** (attempt + 1)  # 2, 4, 8 seconds
                    logger.warning(f"Rate limited on {msg_id}, waiting {wait}s (attempt {attempt + 1})")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"Failed to process {msg_id}: {e}")
                    return  # Non-rate-limit error, skip this message
        logger.error(f"Gave up on {msg_id} after {max_retries} retries")

    async def _process_message(self, msg_id: str):
        """Fetch raw .eml in a single API call, parse everything from it."""
        # Single API call — get raw bytes + metadata (labels, threadId, snippet, size)
        raw_bytes = self._gmail.get_raw_message(msg_id)
        # We still need labels/threadId/snippet which aren't in raw format,
        # so fetch minimal metadata with a fields mask (cheap, small response)
        meta = self._gmail.get_message(msg_id, format="metadata")

        # Parse the raw email
        msg_parsed = email.message_from_bytes(raw_bytes, policy=email.policy.default)

        sender_raw = msg_parsed.get("From", "")
        sender_addr = self._gmail.extract_email_address(sender_raw)
        subject = msg_parsed.get("Subject", "")
        date_str = msg_parsed.get("Date", "")
        to_addr = msg_parsed.get("To", "")
        cc_addr = msg_parsed.get("Cc", "")

        # Extract plain text body
        body_text = ""
        if msg_parsed.is_multipart():
            for part in msg_parsed.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode("utf-8", errors="replace")
                        break
        else:
            if msg_parsed.get_content_type() == "text/plain":
                payload = msg_parsed.get_payload(decode=True)
                if payload:
                    body_text = payload.decode("utf-8", errors="replace")

        # Check for attachments
        has_attachments = any(
            part.get_content_disposition() == "attachment"
            for part in msg_parsed.walk()
        ) if msg_parsed.is_multipart() else False

        labels = meta.get("labelIds", [])
        snippet = meta.get("snippet", "")
        thread_id = meta.get("threadId", "")
        size_bytes = meta.get("sizeEstimate", len(raw_bytes))
        now = datetime.utcnow().isoformat()

        await self._db.execute(
            """INSERT INTO emails (id, thread_id, subject, sender, sender_email,
               recipients, date, snippet, body_text, labels, size_bytes,
               has_attachments, classification, synced_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unclassified', ?, ?)""",
            (
                msg_id, thread_id, subject,
                sender_raw, sender_addr,
                json.dumps({"to": to_addr, "cc": cc_addr}),
                date_str, snippet, body_text,
                json.dumps(labels), size_bytes,
                has_attachments,
                now, now,
            ),
        )

        # Index in FTS5
        await self._db.execute(
            """INSERT INTO emails_fts (rowid, subject, sender, body_text, snippet)
               VALUES ((SELECT rowid FROM emails WHERE id = ?), ?, ?, ?, ?)""",
            (msg_id, subject, sender_raw, body_text, snippet),
        )

        # Run classifier
        result = await self._classifier.classify_email(msg_id)
        if result.classification != "unclassified":
            await self._db.execute(
                """UPDATE emails SET classification = ?, classification_reason = ?,
                   classified_at = ? WHERE id = ?""",
                (result.classification, result.reason, now, msg_id),
            )

        # Upload .eml to R2 for all emails
        if self._r2 is not None:
            try:
                parsed_date = datetime.utcnow()
                try:
                    parsed_date = parsedate_to_datetime(date_str)
                except Exception:
                    pass
                eml_path = self._r2.upload_eml(
                    msg_id, raw_bytes, year=parsed_date.year, month=parsed_date.month
                )
                await self._db.execute(
                    "UPDATE emails SET eml_path = ? WHERE id = ?", (eml_path, msg_id)
                )
            except Exception as e:
                logger.warning(f"R2 upload failed for {msg_id}: {e}")
                self._r2 = None
                logger.warning("R2 disabled for remainder of this sync. Fix R2 config and re-sync.")

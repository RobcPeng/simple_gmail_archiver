import base64
import re
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailService:
    def __init__(self, client_secret_path: Path, token_path: Path):
        self._client_secret_path = client_secret_path
        self._token_path = token_path
        self._creds: Credentials | None = None
        self._service = None

    def authenticate(self) -> bool:
        if self._token_path.exists():
            self._creds = Credentials.from_authorized_user_file(str(self._token_path), SCOPES)
        if self._creds and self._creds.expired and self._creds.refresh_token:
            self._creds.refresh(Request())
            self._save_token()
        if self._creds and self._creds.valid:
            self._service = build("gmail", "v1", credentials=self._creds)
            return True
        return False

    def start_oauth_flow(self, redirect_uri: str = "http://localhost:8000/api/auth/callback"):
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self._client_secret_path), SCOPES,
            redirect_uri=redirect_uri,
        )
        auth_url, _ = flow.authorization_url(prompt="consent")
        self._flow = flow
        return auth_url

    def complete_oauth_flow(self, code: str):
        self._flow.fetch_token(code=code)
        self._creds = self._flow.credentials
        self._save_token()
        self._service = build("gmail", "v1", credentials=self._creds)

    def _save_token(self):
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(self._creds.to_json())

    @property
    def is_authenticated(self) -> bool:
        return self._creds is not None and self._creds.valid

    def list_messages(self, max_results=500, page_token=None, query=None):
        kwargs = {"userId": "me", "maxResults": max_results}
        if page_token:
            kwargs["pageToken"] = page_token
        if query:
            kwargs["q"] = query
        result = self._service.users().messages().list(**kwargs).execute()
        messages = result.get("messages", [])
        next_token = result.get("nextPageToken")
        return messages, next_token

    def get_message(self, msg_id: str, format="full"):
        return self._service.users().messages().get(
            userId="me", id=msg_id, format=format
        ).execute()

    def get_raw_message(self, msg_id: str) -> bytes:
        result = self._service.users().messages().get(
            userId="me", id=msg_id, format="raw"
        ).execute()
        return base64.urlsafe_b64decode(result["raw"])

    def trash_messages(self, msg_ids: list[str]):
        for msg_id in msg_ids:
            self._service.users().messages().trash(userId="me", id=msg_id).execute()

    def delete_messages(self, msg_ids: list[str]):
        for msg_id in msg_ids:
            self._service.users().messages().delete(userId="me", id=msg_id).execute()

    def list_history(self, start_history_id: str):
        try:
            result = self._service.users().history().list(
                userId="me", startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
            ).execute()
            return result.get("history", []), result.get("historyId")
        except Exception as e:
            if "404" in str(e) or "historyId" in str(e).lower():
                return None, None
            raise

    def get_profile(self):
        return self._service.users().getProfile(userId="me").execute()

    @staticmethod
    def parse_headers(headers: list[dict]) -> dict:
        result = {}
        for h in headers:
            name = h["name"].lower()
            if name in ("subject", "from", "to", "cc", "bcc", "date"):
                result[name] = h["value"]
        return result

    @staticmethod
    def extract_email_address(from_header: str) -> str:
        match = re.search(r"<(.+?)>", from_header)
        return match.group(1) if match else from_header

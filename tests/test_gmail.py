import pytest
import base64
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.gmail import GmailService


@pytest.fixture
def gmail():
    with patch("app.services.gmail.build") as mock_build:
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        gs = GmailService.__new__(GmailService)
        gs._service = mock_service
        gs._creds = MagicMock()
        yield gs, mock_service


def test_list_messages(gmail):
    gs, mock_service = gmail
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg_1"}, {"id": "msg_2"}],
        "nextPageToken": "token_abc",
        "resultSizeEstimate": 100,
    }
    messages, next_token = gs.list_messages(max_results=10)
    assert len(messages) == 2
    assert next_token == "token_abc"


def test_get_message(gmail):
    gs, mock_service = gmail
    mock_service.users().messages().get().execute.return_value = {
        "id": "msg_1",
        "threadId": "thread_1",
        "labelIds": ["INBOX"],
        "snippet": "Hello world",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test Subject"},
                {"name": "From", "value": "Alice <alice@example.com>"},
                {"name": "Date", "value": "Mon, 24 Mar 2026 10:00:00 +0000"},
            ],
            "mimeType": "text/plain",
            "body": {"data": base64.urlsafe_b64encode(b"Hello body").decode()},
        },
        "sizeEstimate": 1234,
    }
    msg = gs.get_message("msg_1")
    assert msg["id"] == "msg_1"
    assert msg["snippet"] == "Hello world"


def test_get_raw_message(gmail):
    gs, mock_service = gmail
    raw_content = b"From: test@test.com\r\nSubject: Test\r\n\r\nBody"
    mock_service.users().messages().get().execute.return_value = {
        "id": "msg_1",
        "raw": base64.urlsafe_b64encode(raw_content).decode(),
    }
    raw = gs.get_raw_message("msg_1")
    assert raw == raw_content


def test_parse_message_headers(gmail):
    gs, _ = gmail
    headers = [
        {"name": "Subject", "value": "Invoice"},
        {"name": "From", "value": "Bob <bob@co.com>"},
        {"name": "To", "value": "alice@test.com"},
        {"name": "Date", "value": "Mon, 24 Mar 2026 10:00:00 +0000"},
    ]
    parsed = gs.parse_headers(headers)
    assert parsed["subject"] == "Invoice"
    assert parsed["from"] == "Bob <bob@co.com>"


def test_trash_messages(gmail):
    gs, mock_service = gmail
    gs.trash_messages(["msg_1", "msg_2"])
    assert mock_service.users().messages().trash.call_count == 2


def test_list_history(gmail):
    gs, mock_service = gmail
    mock_service.users().history().list().execute.return_value = {
        "history": [{"messagesAdded": [{"message": {"id": "msg_new"}}]}],
        "historyId": "12345",
    }
    history, new_id = gs.list_history("11111")
    assert new_id == "12345"

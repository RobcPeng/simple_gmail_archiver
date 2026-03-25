import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.r2 import R2Service
from app.config import Settings


@pytest.fixture
def r2():
    settings = Settings(
        r2_account_id="test_account",
        r2_access_key_id="test_key",
        r2_secret_access_key="test_secret",
        r2_bucket_name="test-bucket",
    )
    with patch("app.services.r2.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        service = R2Service(settings)
        service._client = mock_client
        yield service, mock_client


def test_upload_eml(r2):
    service, mock_client = r2
    key = service.upload_eml("msg_123", b"raw email content", year=2026, month=3)
    assert key == "2026/03/msg_123.eml"
    mock_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="2026/03/msg_123.eml",
        Body=b"raw email content",
        ContentType="message/rfc822",
    )


def test_generate_presigned_url(r2):
    service, mock_client = r2
    mock_client.generate_presigned_url.return_value = "https://r2.example.com/signed"
    url = service.get_download_url("2026/03/msg_123.eml")
    assert url == "https://r2.example.com/signed"
    mock_client.generate_presigned_url.assert_called_once()


def test_delete_eml(r2):
    service, mock_client = r2
    service.delete_eml("2026/03/msg_123.eml")
    mock_client.delete_object.assert_called_once_with(
        Bucket="test-bucket", Key="2026/03/msg_123.eml"
    )

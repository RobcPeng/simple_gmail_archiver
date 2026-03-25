import boto3
from app.config import Settings


class R2Service:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
        self._bucket = settings.r2_bucket_name

    def upload_eml(self, message_id: str, raw_bytes: bytes, year: int, month: int) -> str:
        key = f"{year}/{month:02d}/{message_id}.eml"
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=raw_bytes,
            ContentType="message/rfc822",
        )
        return key

    def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_eml(self, key: str):
        self._client.delete_object(Bucket=self._bucket, Key=key)

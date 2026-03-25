from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Paths
    data_dir: Path = Path("data")
    db_path: Path = Path("data/emails.db")

    # R2
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""

    # Gmail OAuth
    credentials_dir: Path = Path("credentials")
    client_secret_path: Path = Path("credentials/client_secret.json")
    token_path: Path = Path("credentials/token.json")

    # Sync
    sync_interval_minutes: int = 60

    # Server
    port: int = 8080
    host: str = "0.0.0.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

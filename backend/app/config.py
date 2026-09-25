from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load backend/.env and workspace root .env with override=True so local project configuration takes precedence over stale OS environment variables
_backend_env = Path(__file__).resolve().parent.parent / ".env"
_root_env = Path(__file__).resolve().parent.parent.parent / ".env"

if _root_env.exists():
    load_dotenv(dotenv_path=_root_env, override=False)
if _backend_env.exists():
    load_dotenv(dotenv_path=_backend_env, override=True)


class Settings(BaseSettings):
    # Mongo
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "phonepe_analyzer"

    # Auth (kept simple: a per-user API key / JWT secret; extend as needed)
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    jwt_refresh_expire_minutes: int = 60 * 24 * 30  # 30 days

    # Redis
    redis_uri: str = "redis://localhost:6379"

    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    s3_bucket_name: str = "phonepe-analyzer-bucket"
    aws_endpoint_url: str | None = None

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Misc
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    upload_dir: str = "/tmp/phonepe_uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

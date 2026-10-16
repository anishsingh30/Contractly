import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

# Compute canonical workspace root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_ENV_PATH = os.path.join(BACKEND_DIR, ".env")
ROOT_ENV_PATH = os.path.join(BASE_DIR, ".env")
CANONICAL_DB_PATH = os.path.join(BASE_DIR, "contractly.db").replace("\\", "/")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=(BACKEND_ENV_PATH, ROOT_ENV_PATH, ".env"),
        extra="ignore"
    )

    PROJECT_NAME: str = "Contractly Legal Operations API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Secret Key for JWT
    SECRET_KEY: str = "contractly_dev_secret_key_change_in_production_9f8a3b2c1d0e"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # 15 minutes for short-lived access tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7     # 7 days for rotating refresh tokens
    SESSION_MAX_LIFETIME_DAYS: int = 30    # 30 days absolute session cutoff
    
    # Cookie Configuration
    ACCESS_TOKEN_COOKIE_NAME: str = "contractly_access_token"
    REFRESH_TOKEN_COOKIE_NAME: str = "contractly_refresh_token"
    SECURE_COOKIES: bool = False  # Set to True in production or via env
    
    # Database: Absolute path to ensure canonical database synchronization
    DATABASE_URL: str = f"sqlite+aiosqlite:///{CANONICAL_DB_PATH}"
    NEON_DATABASE_URL: Optional[str] = None
    AUTO_CREATE_TABLES: bool = False  # Enforces Alembic schema management; prevents silent modifications

    # Database Connection Pool Settings (PostgreSQL only; safely ignored on SQLite)
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT_SECONDS: float = 30.0
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_POOL_PRE_PING: bool = True

    # Auth & API Abuse Protection
    AUTH_RATE_LIMIT_ENABLED: bool = True
    AUTH_LOGIN_MAX_ATTEMPTS: int = 5
    AUTH_LOGIN_WINDOW_SECONDS: int = 300       # 5 minutes lockout after 5 failed attempts
    AUTH_REGISTER_MAX_ATTEMPTS: int = 5
    AUTH_REGISTER_WINDOW_SECONDS: int = 300    # 5 minutes
    AUTH_IP_MAX_REQUESTS_PER_MINUTE: int = 60
    REDIS_URL: Optional[str] = None
    REDIS_REQUIRED: bool = False
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 3.0

    # Autonomous Notification Scheduler (Phase 2)
    NOTIFICATION_SCHEDULER_ENABLED: bool = True
    NOTIFICATION_SCHEDULER_INTERVAL_HOURS: float = 12.0
    NOTIFICATION_SCHEDULER_INITIAL_DELAY_SECONDS: float = 5.0
    
    # Storage
    STORAGE_PROVIDER: str = "local"  # "local" or "s3"
    LOCAL_STORAGE_DIR: str = os.path.join(BASE_DIR, "backend", "storage", "uploads").replace("\\", "/")
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    
    # S3 Storage Configuration (Workstream B)
    S3_BUCKET_NAME: str = ""
    S3_REGION_NAME: str = "us-east-1"
    S3_ENDPOINT_URL: Optional[str] = None
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_SSE_ALGORITHM: Optional[str] = None  # e.g. "AES256" or "aws:kms"
    S3_PRESIGNED_EXPIRATION_SECONDS: int = 900  # 15 minutes short-lived presigned link expiration
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000"
    ]
    
    # AI / LLM Configuration
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-lite-latest"
    GEMINI_API_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_TIMEOUT_SECONDS: float = 35.0
    GEMINI_MAX_QUESTION_LENGTH: int = 1000

    # Email & Notification Settings (Phase 5 Production Delivery)
    EMAIL_SERVICE_ENABLED: bool = False
    EMAIL_ENABLED: bool = False
    EMAIL_PROVIDER: str = "smtp"  # "smtp", "mock", or "transactional"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "notifications@contractly.internal"
    EMAIL_FROM_ADDRESS: Optional[str] = None
    EMAIL_USE_TLS: bool = True
    EMAIL_TIMEOUT_SECONDS: float = 10.0
    EMAIL_MAX_RETRIES: int = 3
    APP_BASE_URL: str = "http://localhost:3000"
    ENFORCE_EMAIL_VERIFICATION: bool = False

    def model_post_init(self, __context):
        # Ensure process os.environ always maintains strict precedence over on-disk .env files
        if os.path.exists(BACKEND_ENV_PATH):
            try:
                with open(BACKEND_ENV_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip()
                            if hasattr(self, k) and v and k not in os.environ:
                                setattr(self, k, v)
            except Exception:
                pass

        # Synchronize alias conventions between EMAIL_SERVICE_ENABLED and EMAIL_ENABLED
        if "EMAIL_SERVICE_ENABLED" in os.environ:
            val = os.environ["EMAIL_SERVICE_ENABLED"].lower() in ("true", "1", "yes")
            self.EMAIL_SERVICE_ENABLED = val
            self.EMAIL_ENABLED = val
        elif "EMAIL_ENABLED" in os.environ:
            val = os.environ["EMAIL_ENABLED"].lower() in ("true", "1", "yes")
            self.EMAIL_SERVICE_ENABLED = val
            self.EMAIL_ENABLED = val
        else:
            self.EMAIL_ENABLED = self.EMAIL_SERVICE_ENABLED or self.EMAIL_ENABLED
            self.EMAIL_SERVICE_ENABLED = self.EMAIL_ENABLED

        # Synchronize EMAIL_FROM and EMAIL_FROM_ADDRESS
        if self.EMAIL_FROM_ADDRESS:
            self.EMAIL_FROM = self.EMAIL_FROM_ADDRESS
        else:
            self.EMAIL_FROM_ADDRESS = self.EMAIL_FROM

        # Support comma-separated ALLOWED_ORIGINS in environment variables
        raw_origins = os.environ.get("ALLOWED_ORIGINS")
        if raw_origins:
            if isinstance(raw_origins, str):
                self.ALLOWED_ORIGINS = [orig.strip() for orig in raw_origins.split(",") if orig.strip()]
        elif isinstance(self.ALLOWED_ORIGINS, str):
            self.ALLOWED_ORIGINS = [orig.strip() for orig in self.ALLOWED_ORIGINS.split(",") if orig.strip()]

        clean_base = (self.APP_BASE_URL or "").strip().rstrip("/")
        if clean_base and clean_base not in self.ALLOWED_ORIGINS:
            self.ALLOWED_ORIGINS.append(clean_base)

        env_name = self.ENVIRONMENT.lower()
        if env_name in ("production", "staging"):
            # Production/Staging MUST use PostgreSQL (Neon)
            if not self.DATABASE_URL or self.DATABASE_URL.startswith("sqlite"):
                if self.NEON_DATABASE_URL:
                    self.DATABASE_URL = self.NEON_DATABASE_URL
                elif os.environ.get("NEON_DATABASE_URL"):
                    self.DATABASE_URL = os.environ["NEON_DATABASE_URL"]
            if not self.DATABASE_URL or not (self.DATABASE_URL.startswith("postgresql") or self.DATABASE_URL.startswith("postgres")):
                raise ValueError(
                    f"CRITICAL CONFIGURATION ERROR: In {env_name} environment, a PostgreSQL database (e.g. Neon) "
                    "must be configured via DATABASE_URL or NEON_DATABASE_URL. SQLite is strictly prohibited."
                )
            # Seamless cloud driver normalization for asyncpg
            import re
            if self.DATABASE_URL.startswith("postgresql://"):
                self.DATABASE_URL = self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif self.DATABASE_URL.startswith("postgres://"):
                self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
            if "sslmode=" in self.DATABASE_URL:
                self.DATABASE_URL = self.DATABASE_URL.replace("sslmode=", "ssl=")
            if "channel_binding=" in self.DATABASE_URL:
                self.DATABASE_URL = re.sub(r'[?&]channel_binding=[^&]+', '', self.DATABASE_URL)
                if '?' not in self.DATABASE_URL and '&' in self.DATABASE_URL:
                    self.DATABASE_URL = self.DATABASE_URL.replace('&', '?', 1)
            key_val = (self.SECRET_KEY or "").strip()
            if (
                not key_val
                or key_val == "contractly_dev_secret_key_change_in_production_9f8a3b2c1d0e"
                or len(key_val) < 32
            ):
                raise ValueError(
                    f"CRITICAL SECURITY CONFIGURATION ERROR: In {env_name} environment, a secure, "
                    "environment-provided SECRET_KEY with at least 32 characters must be configured. "
                    "Development defaults or empty keys are strictly prohibited."
                )
            self.DEBUG = False
            self.SECURE_COOKIES = True
        elif env_name == "development":
            # In local development, ensure canonical SQLite contractly.db unless explicitly overridden via process env
            if not os.environ.get("DATABASE_URL") and not self.DATABASE_URL.startswith("sqlite"):
                if not self.NEON_DATABASE_URL:
                    self.NEON_DATABASE_URL = self.DATABASE_URL
                self.DATABASE_URL = f"sqlite+aiosqlite:///{CANONICAL_DB_PATH}"
            self.SECURE_COOKIES = False
            if self.SECRET_KEY == "contractly_dev_secret_key_change_in_production_9f8a3b2c1d0e":
                import logging
                logging.getLogger("app.config").warning(
                    "SECURITY WARNING: Running with default development SECRET_KEY. "
                    "Ensure a strong, unique secret is supplied via environment in staging/production."
                )

settings = Settings()

def reload_settings() -> Settings:
    """Reloads settings from disk environment files and returns the updated Settings instance."""
    global settings
    new_settings = Settings()
    settings.__dict__.update(new_settings.__dict__)
    return settings

# Ensure local storage directory exists
os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)

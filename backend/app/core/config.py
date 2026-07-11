from pathlib import Path

from pydantic_settings import BaseSettings

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "AI Code Analysis Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./code_analysis.db"
    WORKSPACE_DIR: str = "workspace"
    SERVER_PORT: int = 8001

    # File filtering for analysis
    TEST_DIR_PARTS: list[str] = ["test", "tests"]
    TEST_FILE_PREFIXES: list[str] = ["Test"]
    TEST_FILE_SUFFIXES: list[str] = ["Test.java", "Tests.java", "TestCase.java", "IT.java"]

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_AUTH_TOKEN: str | None = None
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    ANTHROPIC_MODEL: str = "astron-code-latest"
    MAX_TOKENS: int = 4096

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": str(_BACKEND_DIR / ".env"), "env_file_encoding": "utf-8"}


settings = Settings()

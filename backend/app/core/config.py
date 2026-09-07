from pathlib import Path

from pydantic_settings import BaseSettings

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "AI Code Analysis Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "sqlite+aiosqlite:///./code_analysis.db"
    WORKSPACE_DIR: str = "workspace"
    SERVER_PORT: int = 8001

    # File filtering for analysis
    TEST_DIR_PARTS: list[str] = ["test", "tests"]
    TEST_FILE_PREFIXES: list[str] = ["Test"]
    TEST_FILE_SUFFIXES: list[str] = ["Test.java", "Tests.java", "TestCase.java", "IT.java"]

    # Git comparison resource limits
    COMPARISON_MAX_COMMITS: int = 100
    COMPARISON_MAX_FILES: int = 500
    COMPARISON_MAX_FILE_BYTES: int = 1024 * 1024
    COMPARISON_MAX_PATCH_BYTES: int = 5 * 1024 * 1024

    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = "xopqwen36v35b"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.7

    # 多模型池配置
    MODEL_POOL_CONFIG: str = "[]"  # JSON: [{"model_id":"x","base_url":"...","api_key":"...","max_concurrency":3}]
    MODEL_DEFAULT_BASE_URL: str = ""
    MODEL_DEFAULT_API_KEY: str = ""
    MODEL_ROUTER_STRATEGY: str = "least_busy"  # least_busy | round_robin | random
    MODEL_POOL_MAX_QUEUE_SIZE: int = 20
    MODEL_POOL_ACQUIRE_TIMEOUT: int = 30

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": str(_BACKEND_DIR / ".env"), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/neurogenesis.db"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    secret_key: str = "change-me-in-production"
    session_cookie_name: str = "session_id"
    session_expire_hours: int = 168
    log_level: str = "INFO"
    openclaw_enabled: bool = True
    openclaw_workspace: str = "./data/openclaw_workspace"
    openclaw_node_path: str = "npx"
    feishu_app_id: str = ""
    feishu_app_secret: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

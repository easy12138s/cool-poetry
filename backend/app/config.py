from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ==========================================
    # 数据库配置
    # ==========================================
    db_host: str
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str

    # ==========================================
    # 阿里云百炼 API 配置
    # ==========================================
    dashscope_api_key: str
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_model: str = "qwen-plus"

    # ==========================================
    # 上下文管理配置
    # ==========================================
    max_short_term_messages: int = 50

    @property
    def database_url(self) -> str:
        """构建数据库连接URL"""
        return f"mysql+aiomysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()

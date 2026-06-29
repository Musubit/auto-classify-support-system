"""应用配置模块，从环境变量读取配置。"""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Flask 应用配置类。"""

    # ─── Flask ───
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")

    # ─── CORS ───
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "")

    # ─── DeepSeek API ───
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

    # ─── Elasticsearch ───
    ES_HOST: str = os.getenv("ES_HOST", "http://localhost:9200")
    ES_INDEX: str = os.getenv("ES_INDEX", "faq")

    # ─── Redis ───
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ─── NLP ───
    NLP_SERVER_URL: str = os.getenv("NLP_SERVER_URL", "http://localhost:5005")

    # ─── 缓存策略（单位: 秒） ───
    SESSION_TTL: int = 1800  # 会话消息缓存 30 分钟
    FAQ_CACHE_TTL: int = 600  # FAQ 缓存 10 分钟
    INTENT_CACHE_TTL: int = 300  # 意图缓存 5 分钟

    @classmethod
    def validate(cls) -> None:
        """验证关键配置项是否已正确设置。

        Raises:
            ValueError: 当 SECRET_KEY 或生产环境 CORS_ORIGINS 为空时抛出。
        """
        if not cls.SECRET_KEY:
            raise ValueError("SECRET_KEY 环境变量不能为空，请配置 .env")
        if cls.FLASK_ENV != "development" and not cls.CORS_ORIGINS:
            raise ValueError("生产环境必须配置 CORS_ORIGINS 环境变量")

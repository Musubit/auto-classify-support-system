"""应用配置模块，从环境变量读取配置。"""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Flask 应用配置类。"""

    # ─── Flask ───
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")

    # ─── DeepSeek API ───
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

    # ─── Elasticsearch ───
    ES_HOST: str = os.getenv("ES_HOST", "http://localhost:9200")
    ES_INDEX: str = os.getenv("ES_INDEX", "faq")

    # ─── Redis ───
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ─── Rasa ───
    RASA_SERVER_URL: str = os.getenv("RASA_SERVER_URL", "http://localhost:5005")

    # ─── 缓存策略（单位: 秒） ───
    SESSION_TTL: int = 1800  # 会话消息缓存 30 分钟
    FAQ_CACHE_TTL: int = 600  # FAQ 缓存 10 分钟
    INTENT_CACHE_TTL: int = 300  # 意图缓存 5 分钟

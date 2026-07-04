"""Flask 应用工厂模块。"""

import logging
import os

from flask import Flask
from flask_cors import CORS
from flasgger import Swagger

# 必须在加载模型前设置，解决 Windows 下 filelock 死锁 + HF 镜像
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_FILELOCK", "1")

from app.config import Config

logger = logging.getLogger(__name__)


def create_app(config_class: type = Config) -> Flask:
    """创建并配置 Flask 应用实例。

    Args:
        config_class: 配置类，默认使用 Config。

    Returns:
        Flask: 已注册所有蓝图的 Flask 应用实例。
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    config_class.validate()

    # 开发环境默认允许所有来源；生产环境必须在 .env 中配置 CORS_ORIGINS
    cors_origins = app.config.get("CORS_ORIGINS", "")
    if app.config.get("FLASK_ENV") == "development" and not cors_origins:
        cors_origins = "*"
    CORS(app, resources={r"/api/*": {"origins": cors_origins.split(",")}})

    # ─── Swagger / OpenAPI 文档 ───
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/docs",
    }
    swagger_template = {
        "info": {
            "title": "ACSS 电商客服智能问答系统 API",
            "description": "问题自动分类与回答生成客服系统。提供意图分类、情感分析、知识库检索、LLM 流式回答。",
            "version": "0.1.0",
            "contact": {"name": "ACSS Team"},
        },
        "host": "localhost:5000",
        "basePath": "/api",
        "schemes": ["http"],
        "tags": [
            {"name": "系统", "description": "健康检查"},
            {"name": "对话", "description": "SSE 流式聊天"},
        ],
    }
    Swagger(app, config=swagger_config, template=swagger_template)

    # ─── NLP 适配器初始化 ───
    from app.services.nlp_client import NLPClient

    app.extensions["nlp"] = NLPClient(
        base_url=app.config.get("NLP_SERVER_URL", "http://localhost:5005"),
    )

    # ─── SQLite 数据库初始化 ───
    try:
        from app.services.db import init_db

        init_db()
    except Exception as e:
        logger.warning("数据库初始化失败，会话将不持久化: %s", e)

    from app.api import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    # ─── SPA fallback: 非 API 路由返回 index.html ───
    import os as _os

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path: str):
        """SPA catch-all：非 /api 路由返回前端 index.html。"""
        from flask import send_from_directory

        static_dir = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), "static")
        # 如果是静态资源（JS/CSS/图片），直接返回文件
        if path and "." in path:
            full = _os.path.join(static_dir, path)
            if _os.path.isfile(full):
                return send_from_directory(static_dir, path)
        return send_from_directory(static_dir, "index.html")

    # 异步初始化检索服务（不阻塞启动）
    try:
        from app.services.retriever import init_retriever

        init_retriever(app)
    except Exception as e:
        logger.warning("检索服务初始化跳过: %s", e)

    # 异步初始化情感分析服务（不阻塞启动）
    try:
        from app.services.sentiment import init as init_sentiment

        init_sentiment()
    except Exception as e:
        logger.warning("情感分析服务初始化跳过: %s", e)

    logger.info("Flask 应用初始化完成")
    return app

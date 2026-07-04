"""pytest 测试 fixtures — 整个 backend 测试套件共享。"""

import os
from pathlib import Path

import pytest


@pytest.fixture
def temp_db_path(tmp_path: Path, monkeypatch):
    """使用临时目录中的 SQLite 数据库，不影响真实数据。

    通过 monkeypatch 修改 db 模块的 DB_DIR 和 DB_PATH，
    确保所有测试在隔离环境运行。
    """
    import app.services.db as db

    test_db_dir = tmp_path / "data"
    test_db_path = test_db_dir / "acss.db"

    monkeypatch.setattr(db, "DB_DIR", test_db_dir)
    monkeypatch.setattr(db, "DB_PATH", test_db_path)

    db.init_db()
    yield test_db_path


@pytest.fixture
def app_context():
    """提供 Flask 应用上下文 — 最小化创建，不触发服务初始化。

    用于测试依赖 current_app.config 的模块（sentiment / llm 等）。
    """
    from flask import Flask

    app = Flask(__name__)
    app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-key",
        "DEEPSEEK_API_KEY": "sk-test-key",
        "DEEPSEEK_MODEL": "deepseek-v4-flash",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "LLM_BACKEND": "deepseek",
        "OLLAMA_BASE_URL": "http://localhost:11434/v1",
        "OLLAMA_MODEL": "qwen2.5:7b",
        "SENTIMENT_THRESHOLD": "0.85",
        "NLP_SERVER_URL": "http://localhost:5005",
        "ES_HOST": "http://localhost:9200",
        "ES_INDEX": "faq",
        "MAX_CONTEXT_TOKENS": "28000",
    })

    # 设置环境变量让 HF 使用镜像（加速首次模型下载）
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_DISABLE_FILELOCK", "1")

    with app.app_context():
        yield app

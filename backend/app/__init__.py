"""Flask 应用工厂模块。"""

import logging

from flask import Flask
from flask_cors import CORS

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

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    from app.api import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    logger.info("Flask 应用初始化完成")
    return app

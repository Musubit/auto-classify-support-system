"""第三方扩展初始化模块 — Elasticsearch 客户端单例。"""

import logging
from typing import Optional

from elasticsearch import Elasticsearch

from app.config import Config

logger = logging.getLogger(__name__)

_es_client: Optional[Elasticsearch] = None


def get_es_client() -> Elasticsearch:
    """获取 Elasticsearch 客户端单例。

    Returns:
        Elasticsearch: ES 客户端实例。
    """
    global _es_client
    if _es_client is None:
        _es_client = Elasticsearch(Config.ES_HOST)
        logger.info("ES 客户端已初始化: host=%s", Config.ES_HOST)
    return _es_client

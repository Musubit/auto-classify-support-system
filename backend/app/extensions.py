"""第三方扩展初始化模块。

服务层通过此模块获取 Redis 和 ES 客户端实例，
不直接创建连接（遵循 coding-standards.md §1.7 服务层注入约定）。
"""

import logging
from typing import Optional

from elasticsearch import Elasticsearch
from redis import Redis

from app.config import Config

logger = logging.getLogger(__name__)

_redis_client: Optional[Redis] = None
_es_client: Optional[Elasticsearch] = None


def get_redis_client() -> Redis:
    """获取 Redis 客户端单例。

    Returns:
        Redis: Redis 客户端实例。
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(Config.REDIS_URL, decode_responses=True)
        logger.info("Redis 客户端已初始化: url=%s", Config.REDIS_URL)
    return _redis_client


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

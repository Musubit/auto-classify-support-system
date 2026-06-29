"""NLP 模块测试"""
import json
import os
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent


class TestPreprocess:
    """预处理模块测试"""

    def test_tokenize(self):
        """验证 jieba 分词"""
        from src.preprocess import tokenize
        result = tokenize("我的快递到哪了")
        assert isinstance(result, str)
        assert len(result) > 0
        # 分词结果应包含空格分隔的词语
        words = result.split()
        assert len(words) >= 2

    def test_tokenize_empty(self):
        """空文本分词"""
        from src.preprocess import tokenize
        result = tokenize("")
        assert result == ""

    def test_load_stopwords_default(self):
        """默认无停用词"""
        from src.preprocess import load_stopwords
        result = load_stopwords()
        assert isinstance(result, set)
        assert len(result) == 0


class TestTrainingData:
    """训练数据格式测试"""

    def test_training_data_exists(self):
        """训练数据文件存在"""
        data_path = BASE_DIR / "data" / "training.jsonl"
        assert data_path.exists(), "training.jsonl 不存在"

    def test_training_data_format(self):
        """验证 training.jsonl 格式正确"""
        data_path = BASE_DIR / "data" / "training.jsonl"
        with open(data_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) >= 35, f"训练数据不足: {len(lines)} 条（需 >= 35）"

        labels = set()
        for line in lines:
            entry = json.loads(line)
            assert "text" in entry, "缺少 'text' 字段"
            assert "label" in entry, "缺少 'label' 字段"
            assert isinstance(entry["text"], str)
            assert len(entry["text"]) > 0
            labels.add(entry["label"])

        # 验证覆盖所有 7 种意图
        expected_labels = {
            "refund_inquiry", "logistics_inquiry", "product_inquiry",
            "order_inquiry", "complaint", "greeting", "other"
        }
        assert labels == expected_labels, (
            f"意图不完整: 缺少 {expected_labels - labels}"
        )


class TestServer:
    """Flask 服务端测试"""

    @pytest.fixture
    def client(self):
        """创建 Flask 测试客户端"""
        from src.server import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_health(self, client):
        """GET /health 健康检查"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"

    def test_intents(self, client):
        """GET /intents 返回意图列表"""
        resp = client.get("/intents")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "intents" in data
        assert len(data["intents"]) == 7

    def test_parse_missing_text(self, client):
        """POST /parse 缺少 text 字段"""
        resp = client.post("/parse", json={})
        assert resp.status_code == 400

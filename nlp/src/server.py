"""NLP HTTP API 服务"""
import os
import yaml
from flask import Flask, request, jsonify
from flask_cors import CORS

from predict import IntentClassifier
from extract import extract_entities, extract_summary

app = Flask(__name__)
CORS(app)

# 加载分类器（启动时加载模型）
classifier = None

# 加载意图列表
INTENTS = []
config_path = os.path.join(
    os.path.dirname(__file__), "..", "config", "intents.yml"
)
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        INTENTS = config.get("intents", [])


def get_classifier():
    """延迟加载分类器"""
    global classifier
    if classifier is None:
        model_path = os.environ.get(
            "NLP_MODEL_PATH",
            os.path.join(os.path.dirname(__file__), "..", "models")
        )
        classifier = IntentClassifier(model_path)
    return classifier


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "ok", "service": "acss-nlp"})


@app.route("/intents", methods=["GET"])
def list_intents():
    """返回支持的意图列表"""
    return jsonify({"intents": INTENTS})


@app.route("/parse", methods=["POST"])
def parse():
    """单条文本意图分类"""
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "missing 'text' field"}), 400

    text = data["text"]
    clf = get_classifier()
    result = clf.predict(text)
    return jsonify(result)


@app.route("/parse/batch", methods=["POST"])
def parse_batch():
    """批量文本意图分类"""
    data = request.get_json()
    if not data or "texts" not in data:
        return jsonify({"error": "missing 'texts' field"}), 400

    texts = data["texts"]
    clf = get_classifier()
    results = clf.predict_batch(texts)
    return jsonify({"results": results})


@app.route("/extract", methods=["POST"])
def extract():
    """实体抽取"""
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "missing 'text' field"}), 400

    text = data["text"]
    entities = extract_entities(text)
    summary = extract_summary(text)
    return jsonify({"entities": entities, "summary": summary})


if __name__ == "__main__":
    port = int(os.environ.get("NLP_PORT", 5005))
    app.run(host="0.0.0.0", port=port)

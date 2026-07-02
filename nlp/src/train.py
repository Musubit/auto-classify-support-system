"""SetFit 模型训练脚本"""
import json
import os
from pathlib import Path

from datasets import Dataset
from setfit import SetFitModel, SetFitTrainer

from preprocess import tokenize


def load_training_data(data_path: str) -> Dataset:
    """加载 JSONL 格式的训练数据"""
    texts = []
    labels = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            texts.append(tokenize(entry["text"]))
            labels.append(entry["label"])
    return Dataset.from_dict({"text": texts, "label": labels})


def train(data_path: str = None, model_dir: str = None):
    """训练 SetFit 意图分类模型"""
    base_dir = Path(__file__).resolve().parent.parent
    data_path = data_path or str(base_dir / "data" / "training.jsonl")
    model_dir = model_dir or str(base_dir / "models")

    print(f"加载训练数据: {data_path}")
    dataset = load_training_data(data_path)
    print(f"训练样本数: {len(dataset)}")

    # 使用多语言模型作为基础
    model = SetFitModel.from_pretrained(
        "paraphrase-multilingual-MiniLM-L12-v2"
    )

    trainer = SetFitTrainer(
        model=model,
        train_dataset=dataset,
        num_iterations=20,
        num_epochs=5,
        batch_size=16,
    )

    print("开始训练...")
    trainer.train()

    # 保存模型
    os.makedirs(model_dir, exist_ok=True)
    model.save_pretrained(model_dir)
    print(f"模型已保存到: {model_dir}")

    # 简单评估
    print("\n训练完成！使用 predict.py 进行测试。")


if __name__ == "__main__":
    train()

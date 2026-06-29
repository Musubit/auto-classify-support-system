"""模型加载与推理"""
from pathlib import Path

from setfit import SetFitModel

from preprocess import tokenize


class IntentClassifier:
    """SetFit 意图分类器"""

    def __init__(self, model_path: str = None):
        if model_path is None:
            model_path = str(
                Path(__file__).resolve().parent.parent / "models"
            )
        self.model = SetFitModel.from_pretrained(model_path)

    def predict(self, text: str) -> dict:
        """
        预测单个文本的意图
        
        Args:
            text: 用户消息文本
        
        Returns:
            {"intent": "logistics_inquiry", "confidence": 0.95}
        """
        processed = tokenize(text)
        result = self.model.predict([processed])
        intent = result[0]
        
        # 获取置信度（通过预测概率）
        probs = self.model.predict_proba([processed])
        confidence = float(max(probs[0]))
        
        return {"intent": intent, "confidence": round(confidence, 4)}

    def predict_batch(self, texts: list) -> list:
        """
        批量预测意图
        
        Args:
            texts: 文本列表
        
        Returns:
            [{"intent": "...", "confidence": 0.95}, ...]
        """
        processed = [tokenize(t) for t in texts]
        intents = self.model.predict(processed)
        probs = self.model.predict_proba(processed)
        
        results = []
        for i, intent in enumerate(intents):
            confidence = float(max(probs[i]))
            results.append({
                "intent": intent,
                "confidence": round(confidence, 4)
            })
        return results

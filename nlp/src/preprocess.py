"""jieba 分词预处理模块"""
import jieba


def tokenize(text: str) -> str:
    """
    使用 jieba 进行中文分词
    
    Args:
        text: 原始文本
    
    Returns:
        空格分隔的分词结果
    """
    words = jieba.cut(text)
    return " ".join(words)


def load_stopwords(filepath: str = None) -> set:
    """
    加载停用词表
    
    Args:
        filepath: 停用词文件路径，默认为空
    
    Returns:
        停用词集合
    """
    if filepath is None:
        return set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        return set()

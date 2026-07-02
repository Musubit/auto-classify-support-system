"""电商实体抽取模块 — jieba 词性标注 + 正则提取。

支持的实体类型：
- 订单号：如 DD2024070212345、E20240702001
- 手机号：如 13812345678
- 金额：如 ¥100.00、100元、99.9
- 日期：如 2024-07-02、7月2日
- 运单号：如 SF1234567890、YT987654321
- 商品名：jieba 词性标注提取名词短语
- 快递公司：顺丰、圆通、中通、韵达等
"""

import re
from typing import Any

import jieba
import jieba.posseg as pseg

# ─── 正则模式 ───
# 注意：Python 3 默认 re.UNICODE 下 \w 包含中文，\b 在中文和 ASCII 之间失效。
# 使用 (?<!\w) / (?!\w) 替代 \b，或用 re.ASCII 标志。

PATTERNS: dict[str, str] = {
    # 运单号放在 order_id 前面，优先匹配，避免被订单号误吃
    "tracking": r"(?<![a-zA-Z0-9])((?:SF|YT|ZTO|STO|YUNDA|JD|EMS)\d{8,16})(?![a-zA-Z0-9])",
    # 手机号
    "phone":    r"(?<!\d)(1[3-9]\d{9})(?!\d)",
    # 金额
    "amount":   r"(?:¥|￥|人民币\s*)?(\d+\.?\d{0,2})\s*[元块]",
    # 日期
    "date":     r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}月\d{1,2}[日号])",
    # 订单号（在 tracking 之后，避免 SF/YT 等快递前缀被匹配为订单号）
    "order_id": r"(?<![a-zA-Z0-9])([A-Z]{1,3}\d{8,20})(?![a-zA-Z0-9])",
}

# 常见快递公司关键词
COURIER_KEYWORDS = [
    "顺丰", "圆通", "中通", "申通", "韵达", "百世", "德邦",
    "京东物流", "邮政", "EMS", "极兔", "菜鸟", "丹鸟",
]

# 商品相关关键词（用于辅助商品名抽取）
PRODUCT_DESCRIPTORS = [
    "手机", "电脑", "衣服", "裤子", "鞋子", "包", "手表", "耳机",
    "化妆品", "食品", "家电", "家具", "书", "平板", "充电器", "数据线",
]


def extract_entities(text: str) -> dict[str, Any]:
    """从文本中抽取电商相关实体。

    Args:
        text: 用户消息文本。

    Returns:
        dict: 按类型分组的实体，每类为 {values: [...], positions: [...]}。
              无匹配时 values 为空列表。
    """
    entities: dict[str, dict] = {
        "order_id":   {"values": [], "positions": []},
        "phone":      {"values": [], "positions": []},
        "amount":     {"values": [], "positions": []},
        "date":       {"values": [], "positions": []},
        "tracking":   {"values": [], "positions": []},
        "courier":    {"values": [], "positions": []},
        "product":    {"values": [], "positions": []},
    }

    # ─── 1. 正则匹配 ───
    for entity_type, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group(1) if match.lastindex else match.group(0)
            entities[entity_type]["values"].append(value)
            entities[entity_type]["positions"].append({
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0),
            })

    # ─── 2. 快递公司关键词匹配 ───
    for keyword in COURIER_KEYWORDS:
        idx = text.find(keyword)
        if idx >= 0:
            entities["courier"]["values"].append(keyword)
            entities["courier"]["positions"].append({
                "start": idx,
                "end": idx + len(keyword),
                "text": keyword,
            })

    # ─── 3. jieba 词性标注 → 商品名 ───
    # 收集已识别的实体文本，避免商品名中重复
    known_entity_texts: set[str] = set()
    for edata in entities.values():
        for v in edata["values"]:
            known_entity_texts.add(v)

    words = pseg.cut(text)
    current_product_words = []
    for word, flag in words:
        # n=名词, vn=动名词, nz=专名, eng=英文
        if flag in ("n", "vn", "nz", "eng"):
            current_product_words.append(word)
        elif flag in ("x", "w"):
            # 标点/符号，输出之前积累的名词
            if current_product_words:
                _maybe_add_product(entities, current_product_words, known_entity_texts)
                current_product_words = []
        elif word in PRODUCT_DESCRIPTORS:
            current_product_words.append(word)
        # 动词/形容词等 → 截断
        elif flag not in ("uj", "ul", "u", "d", "m", "c"):
            if current_product_words:
                _maybe_add_product(entities, current_product_words, known_entity_texts)
                current_product_words = []

    # 处理末尾残留
    if current_product_words:
        _maybe_add_product(entities, current_product_words, known_entity_texts)

    # ─── 4. 去重：order_id 中排除已识别为 tracking 的值 ───
    tracking_values = set(entities["tracking"]["values"])
    if tracking_values:
        order_data = entities["order_id"]
        order_data["values"] = [v for v in order_data["values"] if v not in tracking_values]
        order_data["positions"] = [p for p in order_data["positions"]
                                   if p["text"] not in tracking_values]

    # ─── 5. 返回（过滤空类） ───
    result = {}
    for etype, edata in entities.items():
        if edata["values"]:
            result[etype] = edata

    return result


def _add_product(entities: dict, product: str, start: int, end: int) -> None:
    """添加商品名实体（去重过滤）。"""
    product = product.strip()
    if len(product) < 2:
        return
    # 过包含数字或已识别的实体文本则跳过
    if re.search(r"\d", product):
        return
    if product in entities["product"]["values"]:
        return
    entities["product"]["values"].append(product)
    entities["product"]["positions"].append({
        "start": start,
        "end": end,
        "text": product,
    })


def _maybe_add_product(
    entities: dict,
    words: list[str],
    known_texts: set[str],
) -> None:
    """从词列表中提取商品名（已过滤噪音）。"""
    product = "".join(words).strip()

    # 过滤：太短、包含已识别的实体文本、含数字
    if len(product) < 2:
        return
    if any(known in product for known in known_texts):
        return
    if re.search(r"\d", product):
        return

    # 只保留：至少含一个商品描述词，或明确的单一名词（如手机号→手机）
    has_descriptor = any(d in product for d in PRODUCT_DESCRIPTORS)
    if has_descriptor or (len(words) == 1 and len(product) <= 4):
        _add_product(entities, product, 0, 0)


def extract_summary(text: str) -> str:
    """抽取实体并返回可读摘要（供前端展示）。

    Args:
        text: 用户消息文本。

    Returns:
        str: 实体摘要字符串。
    """
    entities = extract_entities(text)
    if not entities:
        return ""

    labels = {
        "order_id": "订单号",
        "phone": "手机号",
        "amount": "金额",
        "date": "日期",
        "tracking": "运单号",
        "courier": "快递公司",
        "product": "商品",
    }

    parts = []
    for etype, edata in entities.items():
        label = labels.get(etype, etype)
        parts.append(f"{label}: {', '.join(edata['values'])}")

    return "；".join(parts)

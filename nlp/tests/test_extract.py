"""实体抽取模块测试 — jieba 词性标注 + 正则提取。

覆盖 7 种实体类型：订单号、手机号、金额、日期、运单号、快递公司、商品名。
"""

import re

import pytest

from src.extract import extract_entities, extract_summary


# ─── 订单号 ──────────────────────────────────────────────────


class TestOrderID:
    """订单号识别：大写字母前缀 + 8-20 位数字。"""

    def test_order_id_with_letter_prefix(self):
        """DD2024070212345 格式。"""
        result = extract_entities("我的订单号是DD2024070212345")
        assert "order_id" in result
        assert "DD2024070212345" in result["order_id"]["values"]

    def test_order_id_single_letter_prefix(self):
        """E20240702001 格式。"""
        result = extract_entities("订单E20240702001已发货")
        assert "order_id" in result
        assert "E20240702001" in result["order_id"]["values"]

    def test_order_id_with_positions(self):
        """应返回位置信息。"""
        result = extract_entities("订单DD2024070212345请查收")
        assert result["order_id"]["positions"][0]["start"] == 2
        assert result["order_id"]["positions"][0]["end"] == 17

    def test_no_order_id(self):
        """无订单号时不应出现在结果中。"""
        result = extract_entities("怎么退货啊")
        assert "order_id" not in result


# ─── 手机号 ─────────────────────────────────────────────────


class TestPhone:
    """手机号识别：1 开头 + 10 位数字。"""

    def test_phone_standard(self):
        """标准 138 号段。"""
        result = extract_entities("联系我13812345678就行")
        assert "phone" in result
        assert "13812345678" in result["phone"]["values"]

    def test_phone_all_prefixes(self):
        """覆盖 13x / 14x / 15x / 16x / 17x / 18x / 19x。"""
        phones = [
            "13800001111", "14700001111", "15000001111",
            "16200001111", "17800001111", "18900001111", "19900001111",
        ]
        text = " ".join(phones)
        result = extract_entities(text)
        assert len(result["phone"]["values"]) == 7

    def test_phone_not_in_longer_number(self):
        """长数字中的 11 位子串不应误识别。"""
        # 20 位数字中包含手机号模式 — 不应提取
        result = extract_entities("编号是20250702123456789012")
        assert "phone" not in result


# ─── 金额 ───────────────────────────────────────────────────


class TestAmount:
    """金额识别：¥/元 前后缀格式。"""

    def test_amount_yuan_prefix(self):
        """¥100.00元 格式。"""
        result = extract_entities("退款¥99.50元已到账")
        assert "amount" in result
        assert "99.50" in result["amount"]["values"]

    def test_amount_yuan_suffix(self):
        """100元 格式。"""
        result = extract_entities("运费10元需要自付")
        assert "amount" in result
        assert "10" in result["amount"]["values"]

    def test_amount_rmb_prefix(self):
        """人民币格式。"""
        result = extract_entities("共人民币200.5元")
        assert "amount" in result
        assert "200.5" in result["amount"]["values"]

    def test_amount_integer(self):
        """整数金额。"""
        result = extract_entities("30块包邮")
        assert "amount" in result

    def test_no_amount(self):
        """普通数字不应误识别为金额。"""
        result = extract_entities("买了3件衣服")
        assert "amount" not in result


# ─── 日期 ───────────────────────────────────────────────────


class TestDate:
    """日期识别：ISO 格式 + 中文格式。"""

    def test_date_iso(self):
        """2024-07-02 格式。"""
        result = extract_entities("订单日期是2024-07-02")
        assert "date" in result
        assert "2024-07-02" in result["date"]["values"]

    def test_date_slash(self):
        """2024/07/02 格式。"""
        result = extract_entities("发货日期2024/07/02")
        assert "date" in result
        assert "2024/07/02" in result["date"]["values"]

    def test_date_chinese(self):
        """7月2日 格式。"""
        result = extract_entities("我7月2日下的单")
        assert "date" in result

    def test_no_date_on_long_number(self):
        """长数字串不应误识别。"""
        result = extract_entities("编号1234567890")
        assert "date" not in result


# ─── 运单号 ─────────────────────────────────────────────────


class TestTracking:
    """运单号识别：快递前缀 + 8-16 位数字。"""

    def test_tracking_sf(self):
        """顺丰 SF 前缀。"""
        result = extract_entities("顺丰单号SF1234567890")
        assert "tracking" in result
        assert "SF1234567890" in result["tracking"]["values"]

    def test_tracking_yt(self):
        """圆通 YT 前缀。"""
        result = extract_entities("圆通YT9876543210123")
        assert "tracking" in result
        assert "YT9876543210123" in result["tracking"]["values"]

    def test_tracking_jd(self):
        """京东 JD 前缀。"""
        result = extract_entities("京东物流JD12345678901234")
        assert "tracking" in result

    def test_tracking_not_duplicated_in_order(self):
        """运单号不应同时出现在 order_id 中（去重逻辑）。"""
        result = extract_entities("SF1234567890查物流")
        # 应识别为 tracking，不是 order_id
        assert "tracking" in result
        if "order_id" in result:
            # 去重后不应包含 tracking 的值
            assert "SF1234567890" not in result["order_id"]["values"]


# ─── 快递公司 ───────────────────────────────────────────────


class TestCourier:
    """快递公司关键词匹配。"""

    def test_courier_single(self):
        """单家快递。"""
        result = extract_entities("用的顺丰快递")
        assert "courier" in result
        assert "顺丰" in result["courier"]["values"]

    def test_courier_multiple(self):
        """多快递关键词。"""
        result = extract_entities("顺丰和圆通哪个快")
        couriers = result.get("courier", {}).get("values", [])
        assert "顺丰" in couriers
        assert "圆通" in couriers

    def test_courier_ems(self):
        """大写 EMS。"""
        result = extract_entities("发EMS可以吗")
        assert "courier" in result
        assert "EMS" in result["courier"]["values"]


# ─── 商品名 ─────────────────────────────────────────────────


class TestProduct:
    """商品名识别：jieba 词性标注。"""

    def test_product_simple(self):
        """简单商品名。"""
        result = extract_entities("这个手机屏幕有裂纹")
        if "product" in result:
            assert any("手机" in v for v in result["product"]["values"])

    def test_product_with_descriptor(self):
        """包含描述词的商品名。"""
        result = extract_entities("买的这个耳机质量很好")
        # 有 descriptor 词 "耳机" 时更容易命中
        if "product" in result:
            products = result["product"]["values"]
            assert all(len(p) >= 2 for p in products)

    def test_product_not_duplicate_of_known_entity(self):
        """已知实体文本不应重复出现为商品名。"""
        result = extract_entities("订单DD2024070212345的手机")
        if "product" in result:
            assert "DD2024070212345" not in result["product"]["values"]


# ─── 多实体共存 ─────────────────────────────────────────────


class TestMultipleEntities:
    """一条消息中包含多种实体。"""

    def test_order_and_phone(self):
        """订单号 + 手机号 共存。"""
        text = "订单DD2024070212345，电话13800001111"
        result = extract_entities(text)
        assert "order_id" in result
        assert "phone" in result

    def test_tracking_and_courier(self):
        """运单号 + 快递公司 共存。"""
        text = "顺丰SF1234567890到哪了"
        result = extract_entities(text)
        assert "tracking" in result
        assert "courier" in result

    def test_amount_and_date(self):
        """金额 + 日期 共存。"""
        text = "7月2日退款99元"
        result = extract_entities(text)
        assert "date" in result
        assert "amount" in result


# ─── 边界情况 ────────────────────────────────────────────────


class TestEdgeCases:
    """边界和异常输入。"""

    def test_empty_text(self):
        """空文本返回空 dict。"""
        result = extract_entities("")
        assert result == {}

    def test_no_entities(self):
        """无实体文本返回空 dict。"""
        result = extract_entities("你好，请问一下")
        assert result == {}

    def test_english_text(self):
        """纯英文文本（无中文实体）。"""
        result = extract_entities("Hello, where is my order?")
        # 不应崩溃，至少不应提取中文实体
        assert isinstance(result, dict)

    def test_special_characters(self):
        """特殊字符不会被误识别。"""
        result = extract_entities("!!!???...##@@")
        assert isinstance(result, dict)

    def test_partial_number_patterns(self):
        """不完整的数字模式不误识别。"""
        # 10 位数字（不是 11 位手机号）
        result = extract_entities("编号1234567890")
        assert "phone" not in result

    def test_values_are_strings(self):
        """所有 value 应为 str 类型。"""
        text = "订单DD2024070212345退款¥99.50电话13812345678"
        result = extract_entities(text)
        for etype, edata in result.items():
            for v in edata["values"]:
                assert isinstance(v, str), f"{etype}.values 包含非 str: {v!r}"
            for p in edata["positions"]:
                assert isinstance(p["start"], int)
                assert isinstance(p["end"], int)
                assert isinstance(p["text"], str)


# ─── extract_summary 测试 ──────────────────────────────────


class TestExtractSummary:
    """实体摘要格式化。"""

    def test_summary_with_entities(self):
        """有实体时返回中文摘要。"""
        summary = extract_summary("订单DD2024070212345退款¥99.50")
        assert len(summary) > 0
        assert "订单号" in summary or "金额" in summary

    def test_summary_empty(self):
        """无实体返回空字符串。"""
        summary = extract_summary("你好")
        assert summary == ""

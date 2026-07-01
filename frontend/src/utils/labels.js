/**
 * 标签映射工具 — 将英文标签转换为中文展示名称。
 *
 * 用于意图分类和情感分析的 UI 呈现。
 */

/** 意图英文 → 中文映射。 */
export const INTENT_LABELS = {
  refund_inquiry: '退货咨询',
  logistics_inquiry: '物流查询',
  product_inquiry: '商品咨询',
  order_inquiry: '订单查询',
  complaint: '投诉',
  greeting: '问候',
  other: '其他',
};

/** 情感英文 → 中文映射。 */
export const SENTIMENT_LABELS = {
  positive: '正面',
  negative: '负面',
  neutral: '中性',
};

/**
 * 获取意图中文名称。
 * @param {string} intent - 英文意图标签
 * @returns {string} 中文名称
 */
export function getIntentLabel(intent) {
  return INTENT_LABELS[intent] || intent;
}

/**
 * 获取情感中文名称。
 * @param {string} label - 英文情感标签
 * @returns {string} 中文名称
 */
export function getSentimentLabel(label) {
  return SENTIMENT_LABELS[label] || label;
}

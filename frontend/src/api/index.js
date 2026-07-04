/**
 * 前端 API 封装模块。
 *
 * 提供 axios HTTP 客户端实例和 SSE 流式聊天的 fetch 封装。
 * Vite 开发服务器将 /api/* 请求代理到 http://localhost:5000。
 */
import axios from 'axios';

/** axios 实例，baseURL 为 /api，超时 30 秒。 */
export const http = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

/**
 * 发起 SSE 流式聊天请求。
 *
 * 使用 fetch + ReadableStream 读取 SSE 事件流，
 * 解析 event/data 字段并触发对应回调。
 *
 * @param {string} sessionId - 会话 ID
 * @param {string} message - 用户消息文本
 * @param {object} callbacks - 事件回调
 * @param {function} [callbacks.onIntent] - 收到 intent 事件时调用
 * @param {function} [callbacks.onSentiment] - 收到 sentiment 事件时调用
 * @param {function} [callbacks.onEntity] - 收到 entity 事件时调用
 * @param {function} [callbacks.onToken] - 收到 token 事件时调用
 * @param {function} [callbacks.onDone] - 收到 done 事件时调用
 * @param {function} [callbacks.onError] - 出错或收到 error 事件时调用
 * @returns {Promise<void>}
 */
export async function streamChat(sessionId, message, callbacks = {}) {
  const { onIntent, onSentiment, onEntity, onToken, onDone, onError } = callbacks;

  let response;
  try {
    response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
  } catch (err) {
    if (onError) onError(`网络请求失败: ${err.message}`);
    return;
  }

  if (!response.ok) {
    // 非 2xx 响应 — 尝试读取 JSON 错误
    try {
      const errBody = await response.json();
      if (onError) onError(errBody.message || `请求失败 (${response.status})`);
    } catch {
      if (onError) onError(`请求失败 (${response.status})`);
    }
    return;
  }

  // 读取 SSE 流
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let currentEvent = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // 按空行分割 SSE 事件
      const parts = buffer.split('\n\n');
      // 最后一部分可能不完整，保留到下次处理
      buffer = parts.pop();

      for (const part of parts) {
        if (!part.trim()) continue;

        // 解析 event: 和 data: 行
        for (const line of part.split('\n')) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6);
            try {
              const data = JSON.parse(jsonStr);
              dispatchEvent(currentEvent, data, { onIntent, onSentiment, onEntity, onToken, onDone, onError });
            } catch {
              // JSON 解析失败，跳过
            }
          }
        }
      }
    }
  } catch (err) {
    if (onError) onError(`流式读取中断: ${err.message}`);
  }
}

/**
 * 根据事件类型分发到对应回调。
 *
 * @param {string} event - SSE 事件类型
 * @param {object} data - 解析后的 JSON 数据
 * @param {object} callbacks - 回调集合
 */
function dispatchEvent(event, data, callbacks) {
  switch (event) {
    case 'intent':
      if (callbacks.onIntent) callbacks.onIntent(data);
      break;
    case 'sentiment':
      if (callbacks.onSentiment) callbacks.onSentiment(data);
      break;
    case 'entity':
      if (callbacks.onEntity) callbacks.onEntity(data);
      break;
    case 'token':
      if (callbacks.onToken) callbacks.onToken(data.token);
      break;
    case 'done':
      if (callbacks.onDone) callbacks.onDone(data);
      break;
    case 'error':
      if (callbacks.onError) callbacks.onError(data.message || '未知错误');
      break;
  }
}

// ─── Session API ───

/**
 * 获取会话列表。
 * @returns {Promise<Array>}
 */
export async function listSessions() {
  const { data } = await http.get('/sessions');
  return data.data || [];
}

/**
 * 获取单个会话详情（含消息）。
 * @param {string} sessionId
 * @returns {Promise<{session: object, messages: Array}>}
 */
export async function getSession(sessionId) {
  const { data } = await http.get(`/sessions/${sessionId}`);
  return data.data;
}

/**
 * 删除会话。
 * @param {string} sessionId
 * @returns {Promise<void>}
 */
export async function deleteSessionApi(sessionId) {
  await http.delete(`/sessions/${sessionId}`);
}

// ─── Analytics API ───

/**
 * 获取数据看板聚合统计数据。
 * @returns {Promise<object>}
 */
export async function fetchAnalytics() {
  const { data } = await http.get('/analytics');
  return data.data;
}
